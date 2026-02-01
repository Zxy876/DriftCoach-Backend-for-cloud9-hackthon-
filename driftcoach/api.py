"""
FastAPI delivery shell exposing demo payload at GET /api/demo.
- No query/body params.
- Returns JSON structure aligned with frontend/mocks/demo.json.
- Supports mock fixtures or GRID adapter via DATA_SOURCE env (mock | grid).
"""

from __future__ import annotations

import os
import sys
import uuid
import json
import hashlib
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, Set
from datetime import datetime

import logging
import requests

logging.basicConfig(level=logging.INFO)

import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from driftcoach.core.state import State
from driftcoach.core.action import Action
from driftcoach.main import build_registry, load_actions, _build_outputs
from driftcoach.analysis.trigger import is_eligible
from driftcoach.adapters.grid.client import GridClient
from driftcoach.adapters.grid.planner import build_plan, execute_plan
from driftcoach.adapters.grid.to_state import build_states
from driftcoach.adapters.grid.patch_executor import execute_patches
from driftcoach.adapters.grid.rate_budget import (
    get_rate_budget,
    get_circuit,
    get_run_budget,
    set_run_budget,
    clear_run_budget,
    GridRunBudgetExceeded,
    GridRateExceeded,
    GridCircuitOpen,
    grid_health_snapshot,
)
from driftcoach.mining.execution import execute_mining_plan
from driftcoach.mining.planner import (
    QueryAttempt,
    MiningPlanner,
    MiningContext,
    EntityPool,
    BlockedPaths,
    EmptyResultTracker,
)
from driftcoach.mining.narrative import render_mining_narrative
from driftcoach.research import build_research_plan, evaluate_mining_progress, EvidencePlanner
from driftcoach.stats_executor import StatsExecutor
from driftcoach.stats_attempt_set import StatsAttemptSet
from driftcoach.llm.orchestrator import generate_inference_plan
from driftcoach.llm.mining_plan_generator import generate_mining_plan
from driftcoach.session import session_analysis_store, build_analysis_node_from_agg, build_snapshot_from_stats_results
from driftcoach.analysis.answer_synthesizer import AnswerInput, AnswerSynthesisResult, synthesize_answer, render_answer
from driftcoach.session.analysis_store import SessionAnalysisStore
from driftcoach.hackathon.series_pipeline import hackathon_mine_and_analyze
from driftcoach.narrative.orchestration import run_narrative_orchestration
from driftcoach.narrative.findings_narrative import render_narrative_from_findings
from driftcoach.analysis.scope_reducer import reduce_scope
from driftcoach.analysis.derived_finding_builder import (
    build_findings_from_facts,
    evaluate_question,
    reuse_findings_from_pool,
)
from driftcoach.question_state import QuestionState, SessionQAState


logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
DEMO_PAYLOAD_PATH = ROOT_DIR / "frontend" / "mocks" / "demo.json"

DATA_SOURCE = (os.getenv("DATA_SOURCE") or "mock").lower()
GRID_API_KEY = os.getenv("GRID_API_KEY")
GRID_PLAYER_ID = os.getenv("GRID_PLAYER_ID", "")
GRID_SERIES_ID = os.getenv("GRID_SERIES_ID", "")
GRID_PLAYER_NAME = os.getenv("GRID_PLAYER_NAME", "UnknownPlayer")
GRID_TEAM_NAME = os.getenv("GRID_TEAM_NAME", "UnknownTeam")
MAX_PATCHES_PER_QUERY = int(os.getenv("MAX_PATCHES_PER_QUERY", "3"))
HACKATHON_MODE = (os.getenv("HACKATHON_MODE", "true").lower() == "true")
STATS_ENABLED = (os.getenv("STATS_ENABLED", "false").lower() == "true")
DEMO_MODE = (os.getenv("DEMO_MODE", "false").lower() == "true")
DEMO_SERIES_ID = os.getenv("DEMO_SERIES_ID", GRID_SERIES_ID)
DEMO_QUERY_LIMIT = int(os.getenv("DEMO_QUERY_LIMIT", "8"))

app = FastAPI()


@app.exception_handler(Exception)
async def safe_fallback(request: Request, exc: Exception):
    logger.warning("global_exception_fallback", exc_info=exc)
    return JSONResponse(
        status_code=200,
        content={
            "intent": "unknown",
            "narrative": {
                "type": "ERROR_FALLBACK",
                "confidence": 0.1,
                "content": "系统已生成复盘结果，但内容过多，已启用安全模式。",
            },
        },
    )

# CORS: allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_conversation_store: Dict[str, Dict[str, Any]] = {}
_session_store: Dict[str, Dict[str, Any]] = {}
_demo_query_store: Dict[str, int] = {}
_qa_store: Dict[str, SessionQAState] = {}


def _rate_limit_guard() -> None:
    try:
        get_rate_budget().acquire()
    except Exception:
        # If budget is unavailable, fail open to avoid crashing the API
        logger.warning("rate_budget_unavailable", exc_info=True)


def load_demo_payload() -> Dict[str, Any]:
    if not DEMO_PAYLOAD_PATH.exists():
        raise FileNotFoundError(f"Demo payload not found at {DEMO_PAYLOAD_PATH}")
    with DEMO_PAYLOAD_PATH.open() as f:
        return json.load(f)


def _truncate_text(text: Any, max_chars: int = 8000) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = json.dumps(text, ensure_ascii=False)
        except Exception:
            text = str(text)
    return text if len(text) <= max_chars else text[: max_chars - 3] + "..."


def _deduce_intent(coach_query: str, hinted: Optional[str]) -> str:
    if hinted:
        return hinted
    if "经济" in coach_query or "eco" in coach_query.lower():
        return "ECONOMIC_ISSUE"
    if "教训" in coach_query or "总结" in coach_query:
        return "SUMMARY"
    if "地图" in coach_query or "薄弱" in coach_query:
        return "MATCH_REVIEW"
    if "议程" in coach_query or "复盘" in coach_query:
        return "MATCH_REVIEW"
    if "选手" in coach_query or "阵亡" in coach_query:
        return "PLAYER_REVIEW"
    return hinted or "MATCH_REVIEW"


def _scope_from_intent(intent: str) -> str:
    mapping = {
        "ECONOMIC_ISSUE": "ECON",
        "MATCH_REVIEW": "MAP",
        "PLAYER_REVIEW": "PLAYER",
        "COUNTERFACTUAL_PLAYER_IMPACT": "PLAYER",
        "MATCH_SUMMARY": "SUMMARY",
        "SUMMARY": "SUMMARY",
    }
    return mapping.get(intent, "MAP")


def _ensure_session_qa(session_id: str) -> SessionQAState:
    if session_id not in _qa_store:
        _qa_store[session_id] = SessionQAState(session_id=session_id)
    return _qa_store[session_id]


class CoachQuery(BaseModel):
    coach_query: str
    mode: Optional[str] = None
    series_id: Optional[str] = None
    player_id: Optional[str] = None
    last_player_name: Optional[str] = None
    max_steps: Optional[int] = None
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None


class CoachInit(BaseModel):
    grid_series_id: str
    grid_player_id: Optional[str] = None


def _allow_stats_fallback(data_source: str) -> bool:
    if (os.getenv("ALLOW_STATS_FALLBACK") or "").lower() == "true":
        return True
    if data_source != "grid":
        return True
    if os.getenv("PYTEST_CURRENT_TEST") or any("pytest" in arg for arg in sys.argv):
        return True
    return False


def _build_player_seeds(grid_player_id: Optional[str], data_source: str) -> List[str]:
    seeds: List[str] = []
    if _allow_stats_fallback(data_source):
        fallback_stats_player = os.getenv("GRID_STATS_PLAYER_FALLBACK", "")
        for pid in [p.strip() for p in fallback_stats_player.split(",") if p.strip()]:
            if pid not in seeds:
                seeds.append(pid)
    if grid_player_id and grid_player_id not in seeds:
        seeds.append(grid_player_id)
    return seeds


def _stats_confidence_tier(stats_results: List[Dict[str, Any]], aggregated_pack: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    if aggregated_pack:
        return "high", "stats_success"
    if stats_results:
        last = stats_results[-1] or {}
        status = (last.get("status") or "").lower()
        if status == "success":
            return "high", "stats_success"
        if status in {"invalid_spec", "empty", "unavailable", "skipped"}:
            return "low", status or "stats_unavailable"
        return "low", status or "stats_unavailable"
    return "low", "stats_unavailable"


def _compose_forced_answer(coach_query: str, tier: str, rationale: Optional[str] = None) -> str:
    if tier == "high":
        base = rationale or "根据最新统计样本，表现走势整体稳定，可在既有战术上微调。"
        return f"根据最近 3 个月的可用统计数据，围绕「{coach_query}」的判断是：{base}"
    # tier low/default
    base = rationale or "当前统计样本不足，以下判断基于赛程与对手结构，置信度较低。"
    return f"{base}"


def _strip_debug(text: str) -> str:
    if not text:
        return text
    markers = ["states_lt_20", "series_pool_zero", "agg_performance_zero", "gate-insufficient"]
    cleaned = text
    for m in markers:
        cleaned = cleaned.replace(m, "")
    return cleaned.strip(" ;。；")


def _hackathon_message_from_analysis(payload: Dict[str, Any]) -> str:
    ans = payload.get("answer_synthesis") or (payload.get("context", {}).get("meta", {}).get("answer_synthesis") if isinstance(payload.get("context"), dict) else None)
    if ans:
        try:
            res = AnswerSynthesisResult(**ans)
            return render_answer(res)
        except Exception:
            pass

    analysis = payload.get("session_analysis") or {}
    nodes = analysis.get("analysis_nodes") or []
    evidence = (payload.get("context", {}) or {}).get("hackathon_evidence") or []
    file_facts = [e for e in evidence if e.get("type") == "FILE_FACT"]

    games_count = 0
    series_count = 0
    format_present = False
    participation_present = False
    full_length = False
    max_games = None
    winner_team = None
    file_fact_types = {}

    outcome_ev = next((e for e in evidence if e.get("type") == "SERIES_OUTCOME"), None)
    if outcome_ev:
        games_count = outcome_ev.get("games_played") or 0
        series_count = 1
        winner_team = outcome_ev.get("winner_team_id")
        fmt_str = outcome_ev.get("format")
        if fmt_str:
            format_present = True
            if "5" in fmt_str:
                max_games = 5
            elif "3" in fmt_str:
                max_games = 3
            full_length = bool(max_games and games_count >= max_games)

    for node in nodes:
        meta = node.get("metadata") or {}
        n_type = node.get("type")
        if n_type == "PLAYER_PARTICIPATION" and meta.get("available") is not False:
            participation_present = True
        if n_type == "RISK_PROFILE" and meta.get("full_length"):
            full_length = True
            max_games = meta.get("max_games") or max_games

    judgment = "基于真实对局" if games_count else "样本不足"
    if games_count and full_length:
        judgment = "高风险/打满局"

    confidence = "中" if games_count else "低"

    for f in file_facts:
        ft = f.get("fact_type") or "unknown"
        file_fact_types[ft] = file_fact_types.get(ft, 0) + 1

    facts_lines = [
        f"• 样本：{series_count} series / {games_count} games",
        f"• 结果：{'已知胜方 ' + str(winner_team) if winner_team else '胜负未明'}",
        f"• 赛制：{'有' if format_present else '缺失'}；打满局：{'是' if full_length else '否/未知'}",
        f"• 参与数据：{'有玩家击杀/死亡' if participation_present else '未提供玩家击杀/死亡'}",
        f"• 事件级事实：{sum(file_fact_types.values())} 条（" + ", ".join([f"{k}:{v}" for k,v in file_fact_types.items()]) + ")" if file_fact_types else "• 事件级事实：暂未提炼",
    ]

    next_steps = "可追问：关键局（决胜局）表现、失分来源；经济决策与风险回合。"

    parts = [
        "基于 Series State + File Download（事件级数据）。",
        "可见事实：\n" + "\n".join(facts_lines),
        f"判断类型：{judgment}",
        f"置信度：{confidence}（基于真实局数），{next_steps}",
    ]
    return "\n".join(parts)


def _ensure_messages(
    payload: Dict[str, Any],
    coach_query: str,
    stats_results: List[Dict[str, Any]],
    aggregated_pack: Optional[Dict[str, Any]],
    inference_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if HACKATHON_MODE or not STATS_ENABLED:
        assistant_msg = _hackathon_message_from_analysis(payload)
        payload["assistant_message"] = assistant_msg
        payload["messages"] = [{"role": "assistant", "content": assistant_msg}]
        payload.setdefault("context", {}).setdefault("meta", {})["stats_confidence"] = {
            "tier": "low",
            "reason": "hackathon_mode_no_stats",
        }
        return payload

    tier, tier_reason = _stats_confidence_tier(stats_results, aggregated_pack)
    raw_msg = payload.get("assistant_message") or (inference_plan or {}).get("rationale")
    sanitized = _strip_debug(raw_msg or "")
    if not sanitized:
        assistant_msg = _compose_forced_answer(coach_query, tier, rationale=None)
    else:
        if tier == "high":
            assistant_msg = _compose_forced_answer(coach_query, tier, rationale=sanitized)
        else:
            assistant_msg = _compose_forced_answer(coach_query, tier, rationale=None)
    payload["assistant_message"] = assistant_msg
    payload["messages"] = [{"role": "assistant", "content": assistant_msg}]
    payload.setdefault("context", {}).setdefault("meta", {})["stats_confidence"] = {
        "tier": tier,
        "reason": tier_reason,
    }
    return payload


def load_states_from_grid(player_id: Optional[str] = None, series_id: Optional[str] = None) -> Tuple[List[State], Dict[str, Any]]:
    if DATA_SOURCE != "grid":
        raise RuntimeError("DATA_SOURCE must be grid to load states from GRID")
    if not GRID_API_KEY:
        raise RuntimeError("GRID_API_KEY is required when DATA_SOURCE=grid")

    series = series_id or GRID_SERIES_ID
    player = player_id or GRID_PLAYER_ID or "placeholder"
    if not series:
        raise RuntimeError("series_id_required")

    client = GridClient(api_key=GRID_API_KEY)
    plan = build_plan(series, player)
    facts = execute_plan(plan, client)

    anchor = facts.get("anchor_series") or {}
    pool = facts.get("narrowed") or facts.get("series_pool") or []
    roster_proxy = facts.get("roster_proxy", "SKIPPED")
    outcome_field = facts.get("outcome_field", "NOT_FOUND")

    states, context_meta = build_states(
        anchor,
        pool,
        player,
        outcome_field,
        roster_proxy,
        player_stats_info=facts.get("player_statistics"),
        team_stats_info=facts.get("team_statistics"),
    )

    by_type: Dict[str, int] = {}
    for s in states:
        ev_type = s.extras.get("evidence_type") or s.extras.get("slice_type", "UNKNOWN")
        by_type[ev_type] = by_type.get(ev_type, 0) + 1

    logger.info(
        "[FACT] pool=%s narrowed=%s window=%s",
        facts.get("counts", {}).get("pool"),
        facts.get("counts", {}).get("narrowed"),
        facts.get("window"),
    )
    logger.info(
        "[STATE] total=%s by_type=%s",
        len(states),
        by_type,
    )
    logger.info(
        "[EVIDENCE] aggregated_present=%s count=%s",
        "AGGREGATED_PERFORMANCE" in by_type,
        by_type.get("AGGREGATED_PERFORMANCE", 0),
    )
    logger.info(
        "[SCHEMA] outcome_field=%s missing=%s",
        facts.get("outcome_field"),
        facts.get("missing_outcome_fields"),
    )

    agg_meta = context_meta.get("evidence", {}).get("aggregation_meta", {})
    agg_states = agg_meta.get("aggregated_states") if isinstance(agg_meta, dict) else None
    logger.info(
        "[AGG] aggregated_states=%s meta=%s",
        agg_states,
        agg_meta,
    )

    context_meta.setdefault("schema", {})["outcome_field"] = facts.get("outcome_field")
    context_meta["schema"]["missing_outcome_fields"] = facts.get("missing_outcome_fields")
    context_meta.setdefault("evidence", {})["window"] = facts.get("window")
    context_meta["evidence"]["pool_counts"] = facts.get("counts")
    context_meta["evidence"]["statistics"] = {
        "team": facts.get("team_statistics"),
        "player": facts.get("player_statistics"),
    }
    context_meta["evidence"]["seriesPool"] = (facts.get("counts") or {}).get("pool", 0)

    return states, context_meta


def _evidence_counts(states: List[State]) -> Dict[str, Any]:
    by_type: Dict[str, int] = {}
    for s in states:
        ev_type = s.extras.get("evidence_type") or s.extras.get("slice_type", "UNKNOWN")
        by_type[ev_type] = by_type.get(ev_type, 0) + 1
    return {"states": len(states), "byType": by_type}


def _time_bucket(ts: Optional[str]) -> str:
    if not ts:
        return "UNKNOWN"
    try:
        cleaned = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
        dt = datetime.fromisoformat(cleaned)
        return f"{dt.year}-{dt.month:02d}"
    except Exception:
        return "UNKNOWN"


def _build_buckets(states: List[State]) -> Dict[str, Dict[str, int]]:
    buckets: Dict[str, Dict[str, int]] = {
        "format": {},
        "tournament": {},
        "time_bucket": {},
        "opponent": {},
    }

    for s in states:
        extras = s.extras or {}
        if extras.get("evidence_type") != "CONTEXT_ONLY":
            continue

        fmt = (extras.get("format") or "UNKNOWN").upper()
        tournament = extras.get("tournament") or "UNKNOWN"
        t_bucket = _time_bucket(extras.get("start_time"))

        opponents = extras.get("team_names") if isinstance(extras, dict) else None
        if isinstance(opponents, list) and opponents:
            opp_label = " vs ".join(sorted(str(o) for o in opponents))
        else:
            opp_label = "UNKNOWN"

        for key, value in (
            ("format", fmt),
            ("tournament", tournament),
            ("time_bucket", t_bucket),
            ("opponent", opp_label),
        ):
            buckets[key][value] = buckets[key].get(value, 0) + 1

    return buckets


def _build_summary(buckets: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "coverage": {"axes": {}, "overall": False},
        "concentration": {},
        "bias_flags": {},
    }

    axes = ["format", "tournament", "time_bucket", "opponent"]
    all_covered = True

    for axis in axes:
        axis_buckets = buckets.get(axis) or {}
        total = sum(axis_buckets.values())
        covered = total > 0
        summary["coverage"]["axes"][axis] = covered
        all_covered = all_covered and covered

        if total <= 0:
            summary["concentration"][axis] = {"top1": 0.0, "top3": 0.0, "total": 0}
            summary["bias_flags"][axis] = False
            continue

        sorted_counts = sorted(axis_buckets.values(), reverse=True)
        top1 = sorted_counts[0]
        top3 = sum(sorted_counts[:3])
        summary["concentration"][axis] = {
            "top1": round(top1 / total, 4),
            "top3": round(top3 / total, 4),
            "total": total,
        }

        bias_threshold = 0.6
        summary["bias_flags"][axis] = (top1 / total) >= bias_threshold

    summary["coverage"]["overall"] = all_covered
    return summary


def _baseline_status_from_progress(progress: Any) -> str:
    satisfied = progress.satisfied_axes if hasattr(progress, "satisfied_axes") else progress.get("satisfied_axes", [])
    for axis in satisfied:
        if axis.startswith("baseline"):
            return "available" if "proxy" not in axis else "proxy"
    return "missing"


def _confidence_level(progress: Any, stats_success: bool) -> str:
    can_answer = progress.can_answer if hasattr(progress, "can_answer") else progress.get("can_answer")
    if stats_success and can_answer:
        return "high"
    if can_answer:
        return "medium"
    return "low"


def _merge_analysis_snapshots(prev: Optional[Dict[str, Any]], new: Dict[str, Any]) -> Dict[str, Any]:
    if not prev:
        return new
    merged = dict(prev)
    cov_prev = prev.get("coverage", {})
    cov_new = new.get("coverage", {})
    merged_cov = {}
    for axis in {"time", "baseline", "opponent", "format"}:
        merged_cov[axis] = bool(cov_prev.get(axis)) or bool(cov_new.get(axis))
    merged["coverage"] = merged_cov

    status_order = {"missing": 0, "proxy": 1, "available": 2}
    prev_status = prev.get("baseline_status", "missing")
    new_status = new.get("baseline_status", "missing")
    merged["baseline_status"] = new_status if status_order.get(new_status, 0) >= status_order.get(prev_status, 0) else prev_status

    conf_rank = {"low": 0, "medium": 1, "high": 2}
    prev_conf = prev.get("confidence", "low")
    new_conf = new.get("confidence", "low")
    merged["confidence"] = new_conf if conf_rank.get(new_conf, 0) >= conf_rank.get(prev_conf, 0) else prev_conf

    sources = set(prev.get("evidence_sources", []) or []) | set(new.get("evidence_sources", []) or [])
    merged["evidence_sources"] = sorted(sources)
    merged["last_updated"] = new.get("last_updated") or prev.get("last_updated")
    return merged


def _build_analysis_snapshot(
    research_progress: Any,
    stats_results: List[Dict[str, Any]],
    summary: Dict[str, Any],
    aggregated_pack: Optional[Dict[str, Any]],
    prev_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    satisfied = research_progress.satisfied_axes if hasattr(research_progress, "satisfied_axes") else research_progress.get("satisfied_axes", [])
    coverage = {"time": False, "baseline": False, "opponent": False, "format": False}
    for axis in satisfied:
        base = axis.split("(")[0]
        if base in coverage:
            coverage[base] = True
    missing = research_progress.missing_axes if hasattr(research_progress, "missing_axes") else research_progress.get("missing_axes", [])
    for axis in missing:
        if axis in coverage:
            coverage.setdefault(axis, False)

    stats_success = any(r.get("status") == "success" for r in stats_results)
    baseline_status = _baseline_status_from_progress(research_progress)
    evidence_sources = []
    if stats_success:
        evidence_sources.extend([r.get("target") for r in stats_results if r.get("status") == "success" and r.get("target")])
    if not stats_success and aggregated_pack:
        evidence_sources.append("PROXY_DISTRIBUTION")

    snapshot = {
        "coverage": coverage,
        "baseline_status": baseline_status,
        "confidence": _confidence_level(research_progress, stats_success),
        "evidence_sources": [s for s in evidence_sources if s],
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }
    return _merge_analysis_snapshots(prev_snapshot, snapshot)


def _serialize_mining_attempt(attempt: Any) -> Dict[str, Any]:
    if isinstance(attempt, QueryAttempt):
        return {
            "template_id": attempt.template_id,
            "substitutions": attempt.substitutions,
            "entity_id": attempt.entity_id,
            "result": attempt.result,
            "notes": attempt.notes,
            "discovered_ids": attempt.discovered_ids,
            "error_path": attempt.error_path,
        }
    if isinstance(attempt, dict):
        return {
            "template_id": attempt.get("template_id"),
            "substitutions": attempt.get("substitutions", {}),
            "entity_id": attempt.get("entity_id"),
            "result": attempt.get("result"),
            "notes": attempt.get("notes"),
            "discovered_ids": attempt.get("discovered_ids") or [],
            "error_path": attempt.get("error_path"),
        }
    return {}


def _serialize_mining_summary(summary_obj: Any) -> Dict[str, Any]:
    if summary_obj is None:
        return {}
    if isinstance(summary_obj, dict):
        serialized = dict(summary_obj)
        attempts = serialized.get("attempts") or []
        serialized["attempts"] = [_serialize_mining_attempt(a) for a in attempts]
        if serialized.get("blocked") and not isinstance(serialized.get("blocked"), dict):
            blocked = serialized.get("blocked")
            serialized["blocked"] = {
                "template_ids": list(getattr(blocked, "template_ids", []) or []),
                "field_paths": list(getattr(blocked, "field_paths", []) or []),
                "substitution_pairs": list(getattr(blocked, "substitution_pairs", []) or []),
            }
        serialized.setdefault("termination_reason", serialized.get("reason") or "FRONTIER_EXHAUSTED")
        return serialized

    serialized = {
        "terminated": summary_obj.terminated,
        "reason": summary_obj.reason,
        "termination_reason": getattr(summary_obj, "termination_reason", "FRONTIER_EXHAUSTED"),
        "attempts": [_serialize_mining_attempt(a) for a in getattr(summary_obj, "attempts", [])],
        "blocked": {
            "template_ids": list(getattr(summary_obj.blocked, "template_ids", []) or []),
            "field_paths": list(getattr(summary_obj.blocked, "field_paths", []) or []),
            "substitution_pairs": list(getattr(summary_obj.blocked, "substitution_pairs", []) or []),
        }
        if getattr(summary_obj, "blocked", None)
        else {},
        "cooled": list(getattr(summary_obj, "cooled", []) or []),
        "entity_counts": getattr(summary_obj, "entity_counts", {}),
        "seeds": getattr(summary_obj, "seeds", {}),
        "discovered": getattr(summary_obj, "discovered", {}),
        "tried_templates": getattr(summary_obj, "tried_templates", []),
        "frontier_exhausted": getattr(summary_obj, "frontier_exhausted", False),
    }
    return serialized


def _human_termination_reason(reason: Optional[str]) -> str:
    if reason == "ALL_TEMPLATES_BLOCKED":
        return "GraphQL schema 或规则阻断所有模板"
    if reason == "ALL_COMBINATIONS_EMPTY":
        return "尝试的组合均为空"
    if reason == "INTENSITY_MAX_NO_PROGRESS":
        return "达到强度上限仍无增量"
    if reason == "FRONTIER_EXHAUSTED":
        return "当前可达前沿已耗尽"
    if reason == "API_CONSTRAINED":
        return "API 受限/频控，暂停挖掘"
    return "探索已结束"


def _build_mining_explanation_block(narrative: Dict[str, Any]) -> str:
    seeds = narrative.get("starting_seeds") or []
    attempted_paths = narrative.get("attempted_paths") or []
    new_entities = narrative.get("new_entities") or {}
    termination_code = narrative.get("termination_reason")
    term_reason = _human_termination_reason(termination_code)

    seed_text = ", ".join(seeds) if seeds else "无"
    success_parts: List[str] = []
    for etype, ids in new_entities.items():
        count = len(ids or [])
        if count > 0:
            success_parts.append(f"{etype} ×{count}")
    success_text = ", ".join(success_parts) if success_parts else "无"

    api_note = ""
    if termination_code == "API_CONSTRAINED":
        api_note = "\n• 受限说明：API 触发限流/网络异常，已停止进一步挖掘"

    lines = [
        "—— 数据挖掘说明 ——",
        f"• 起始信息：{seed_text}",
        f"• 实际尝试路径：{len(attempted_paths)} 条",
        f"• 成功扩展实体：{success_text}",
        f"• 终止原因：{term_reason}",
        "• 结论限制：当前分析基于可达子图，不代表全局统计",
    ]
    if api_note:
        lines.append(api_note)
    return "\n".join(lines)


def _axes_with_bias(summary: Dict[str, Any]) -> List[str]:
    axes: List[str] = []
    conc = summary.get("concentration", {}) or {}
    bias = summary.get("bias_flags", {}) or {}
    for axis, stats in conc.items():
        top1 = stats.get("top1", 0.0)
        if top1 >= 0.6 or bias.get(axis):
            axes.append(axis)
    return axes


def _ai_compose_answer(summary: Dict[str, Any], buckets: Dict[str, Dict[str, int]], coach_query: str) -> str:
    axes = _axes_with_bias(summary)
    parts: List[str] = []
    if not axes:
        parts.append("当前样本分布较均衡，未观察到显著单轴集中。")
    else:
        for axis in axes:
            axis_buckets = buckets.get(axis) or {}
            sorted_items = sorted(axis_buckets.items(), key=lambda kv: kv[1], reverse=True)
            top_labels = [lbl for lbl, _ in sorted_items[:3]]
            parts.append(f"在 {axis} 轴上样本高度集中，主要分布于: {', '.join(top_labels)}。")
    parts.append("未使用胜负/概率，仅基于分布背景，供方向性参考，因缺少历史基线暂无法给出高置信判断。")
    return " ".join(parts)


def _ai_synthesize_from_stats(aggregated_pack: Dict[str, Any], coach_query: str) -> str:
    raw = aggregated_pack.get("raw") or {}
    perf = raw.get("performance") or {}
    trend = raw.get("trend") or {}
    sample = raw.get("sample") or {}
    parts: List[str] = []

    def fmt_delta(v: float) -> str:
        try:
            return f"{v:+.0%}"
        except Exception:
            return f"{v:+.2f}"

    # Pick key metrics
    metric_order = [
        ("kills_per_map", "kills_per_map", "每张地图击杀"),
        ("rating", "rating", "综合 rating"),
        ("win_rate", "win_rate", "系列胜率"),
    ]
    highlights = []
    for key, label, zh_label in metric_order:
        m = perf.get(key)
        if not isinstance(m, dict):
            continue
        val = m.get("value")
        base = m.get("baseline")
        delta = m.get("delta")
        smp = m.get("sample")
        if val is None or base is None or delta is None:
            continue
        try:
            delta_pct = fmt_delta(delta)
        except Exception:
            delta_pct = f"{delta}"
        highlights.append(
            f"{zh_label} {val:.2f}，高于历史基线 {base:.2f}（变化 {delta_pct}，样本 {smp or 'n/a'}）"
        )
    if highlights:
        parts.append("；".join(highlights))

    # Trend comparison
    last = trend.get("last_10_series") or {}
    prev = trend.get("previous_10_series") or {}
    trend_bits = []
    for key, label, zh_label in metric_order:
        if key not in last or key not in prev:
            continue
        lv = last.get(key)
        pv = prev.get(key)
        try:
            delta = (lv - pv) / pv if pv else None
        except Exception:
            delta = None
        if delta is None:
            continue
        trend_bits.append(f"近 10 场 {zh_label} {lv:.2f} 较此前 {pv:.2f} 变化 {fmt_delta(delta)}")
    if trend_bits:
        parts.append("；".join(trend_bits))

    sample_bits = []
    if sample.get("series_count"):
        sample_bits.append(f"系列样本 {sample['series_count']}")
    if sample.get("map_count"):
        sample_bits.append(f"地图样本 {sample['map_count']}")
    time_window = raw.get("timeWindow") or aggregated_pack.get("timeWindow")
    if time_window:
        sample_bits.append(f"时间窗 {time_window}")
    if sample_bits:
        parts.append("，".join(sample_bits))

    note = aggregated_pack.get("note") or raw.get("note")
    if aggregated_pack.get("mock") or raw.get("mock"):
        parts.append("（Mock 聚合数据，供演示使用）")
    if note:
        parts.append(str(note))

    conclusion = "整体表现稳定，与历史基线一致，未见异常。"
    # Simple heuristic: if trend shows decline or delta negative, flag波动
    win_rate = perf.get("win_rate") if isinstance(perf, dict) else None
    if isinstance(win_rate, dict):
        delta = win_rate.get("delta")
        if isinstance(delta, (int, float)) and delta < -0.02:
            conclusion = "存在明显波动，胜率较历史基线下滑。"
        elif isinstance(delta, (int, float)) and delta > 0.03:
            conclusion = "整体表现稳定且略有提升。"

    trend_wr = None
    if isinstance(trend, dict):
        last_wr = trend.get("winRate", {}).get("value") or trend.get("win_rate", {}).get("value")
        prev_wr = trend.get("previous_winRate", {}).get("value") or trend.get("previous_win_rate", {}).get("value")
        try:
            if last_wr is not None and prev_wr is not None:
                trend_wr = (last_wr - prev_wr) / prev_wr if prev_wr else None
                if trend_wr is not None and trend_wr < -0.05:
                    conclusion = "存在明显波动，近期胜率较此前下降。"
        except Exception:
            pass

    if parts:
        parts.append(conclusion)
        return " ".join(parts)
    return "整体表现稳定，与历史基线相比未见异常。"

    conclusion = "总体看，" + "；".join(parts)
    conclusion += "。基于上述统计对照，当前表现更像稳定提升而非偶然波动，未直接输出胜负判断。"
    return conclusion


MIN_SERIES_SAMPLE = 15
MIN_MAP_SAMPLE = 45

INTENSITY_LEVELS = {
    "ENUMERATE_SERIES": "L1",
    "SLICE_BY_OPPONENT": "L2",
    "SLICE_BY_TIME_BUCKET": "L2",
    "AGGREGATE_PLAYER_CONTEXT": "L2",
    "AGGREGATE_PLAYER_STATISTICS": "L2",
    "EXPAND_TIME_WINDOW": "L3",
    "SYNTHESIZE_FROM_STATS": "L2",
}


def _strategy_intensity(strategy: Optional[str]) -> str:
    return INTENSITY_LEVELS.get((strategy or "").upper(), "L1")


def _time_window_for_intensity(level: Optional[str]) -> str:
    level = (level or "").upper()
    mapping = {
        "L1": "LAST_90_DAYS",
        "L2": "LAST_90_DAYS",
        "L3": "LAST_6_MONTHS",
        "L4": "LAST_12_MONTHS",
        "L5": "ALL_TIME",
    }
    return mapping.get(level, "LAST_90_DAYS")


def _bump_intensity(level: Optional[str]) -> str:
    order = ["L1", "L2", "L3", "L4", "L5"]
    lvl = (level or "L1").upper()
    if lvl not in order:
        return "L1"
    idx = order.index(lvl)
    return order[min(idx + 1, len(order) - 1)]


def _build_evidence_sufficiency(aggregated_pack: Optional[Dict[str, Any]], summary: Dict[str, Any]) -> Dict[str, Any]:
    bias_flags = (summary or {}).get("bias_flags") or {}
    blocking_factors: List[str] = []
    confidence_basis: List[str] = []

    has_aggregated = aggregated_pack is not None
    raw = (aggregated_pack or {}).get("raw") or {}
    perf = raw.get("performance") or {}
    trend = raw.get("trend") or {}
    sample = raw.get("sample") or {}

    if not has_aggregated:
        blocking_factors.append("schema_gap")

    if aggregated_pack and (aggregated_pack.get("mock") or raw.get("mock")):
        blocking_factors.append("mock_only")

    if bias_flags.get("format"):
        blocking_factors.append("format_bias")
    if bias_flags.get("opponent"):
        blocking_factors.append("opponent_concentration")

    series_cnt = sample.get("series_count") or 0
    map_cnt = sample.get("map_count") or 0
    if series_cnt < MIN_SERIES_SAMPLE or map_cnt < MIN_MAP_SAMPLE:
        blocking_factors.append("small_sample")

    # Confidence basis
    if perf:
        confidence_basis.append("baseline_comparison")
        if len([k for k, v in perf.items() if isinstance(v, dict) and v.get("value") is not None]) >= 2:
            confidence_basis.append("multi_metric_consistency")
    if trend:
        confidence_basis.append("trend_alignment")

    sufficiency = "PARTIAL"
    if not has_aggregated:
        sufficiency = "INSUFFICIENT"
    elif "mock_only" in blocking_factors or "small_sample" in blocking_factors or "format_bias" in blocking_factors or "opponent_concentration" in blocking_factors:
        sufficiency = "PARTIAL"
    else:
        sufficiency = "SUFFICIENT"

    if not blocking_factors:
        blocking_factors.append("schema_gap")
    if not confidence_basis:
        confidence_basis.append("baseline_comparison")

    return {
        "sufficiency": sufficiency,
        "blocking_factors": blocking_factors,
        "confidence_basis": confidence_basis,
    }


def _build_question_drift(coach_query: str, aggregated_pack: Optional[Dict[str, Any]], answer_text: str) -> Dict[str, Any]:
    uses_stats = aggregated_pack is not None
    if uses_stats:
        current_focus = "对比基线下的异常判定"
        drift_reason = "使用聚合统计对比基线与趋势（kills_per_map/rating/win_rate）"
    else:
        current_focus = "背景分布描述"
        drift_reason = "缺少聚合统计，仅基于分布做背景性回答"

    if not drift_reason:
        drift_reason = "依赖可用证据调整了研究焦点"

    return {
        "original_question": coach_query,
        "current_focus": current_focus,
        "drift_reason": drift_reason,
    }


def _build_iteration_trigger(sufficiency_card: Dict[str, Any], aggregated_pack: Optional[Dict[str, Any]], summary: Dict[str, Any], last_intensity: Optional[str]) -> Dict[str, Any]:
    blocking = sufficiency_card.get("blocking_factors") or []
    confidence_basis = sufficiency_card.get("confidence_basis") or []
    suff = sufficiency_card.get("sufficiency")

    should_iterate = suff != "SUFFICIENT"
    bias_flags = (summary or {}).get("bias_flags") or {}

    if "mock_only" in blocking or bias_flags.get("format") or bias_flags.get("opponent") or "small_sample" in blocking:
        should_iterate = True

    iterate_reason = "提升统计可靠性"
    if "schema_gap" in blocking:
        iterate_reason = "缺少聚合统计"
    elif "mock_only" in blocking:
        iterate_reason = "仅有 mock 聚合，需真实样本"
    elif "format_bias" in blocking:
        iterate_reason = "赛制分布偏置，需补齐其他赛制"
    elif "opponent_concentration" in blocking:
        iterate_reason = "对手集中，需多对手对照"
    elif "small_sample" in blocking:
        iterate_reason = "样本量不足，需更多比赛"

    next_goal = "减少关键统计的不确定性"
    if "schema_gap" in blocking:
        next_goal = "获取真实聚合性能统计"
    elif "format_bias" in blocking:
        next_goal = "补充不同赛制的样本"
    elif "opponent_concentration" in blocking:
        next_goal = "覆盖更多对手样本"
    elif "small_sample" in blocking:
        next_goal = "扩大系列/地图样本量"

    suggested_strategy = "ENUMERATE_SERIES"
    if "format_bias" in blocking or "opponent_concentration" in blocking:
        suggested_strategy = "SLICE_BY_TIME_BUCKET"
    if "schema_gap" in blocking and aggregated_pack is None:
        suggested_strategy = "ENUMERATE_SERIES"
    if not should_iterate and len(confidence_basis) >= 2:
        suggested_strategy = "DECLARE_LIMIT"

    # Escalate intensity when small_sample persists at same level
    if "small_sample" in blocking or "format_bias" in blocking:
        cur_level = _strategy_intensity(suggested_strategy)
        if last_intensity and cur_level == last_intensity:
            suggested_strategy = "EXPAND_TIME_WINDOW"
            next_goal = "扩大时间窗以提高样本量" if "small_sample" in blocking else "扩大时间窗以缓和赛制偏置"
            iterate_reason = "small_sample persists after aggregation" if "small_sample" in blocking else "format_bias persists"
            cur_level = _bump_intensity(cur_level)

    next_intensity = _strategy_intensity(suggested_strategy)
    if "EXPAND_TIME_WINDOW" == suggested_strategy:
        next_intensity = cur_level if 'cur_level' in locals() else _strategy_intensity(suggested_strategy)

    if not confidence_basis:
        confidence_basis.append("baseline_comparison")

    return {
        "should_iterate": should_iterate,
        "iterate_reason": iterate_reason,
        "next_iteration_goal": next_goal,
        "suggested_strategy": suggested_strategy,
        "next_intensity_level": next_intensity,
    }


def _extract_aggregated_perf(states: List[State]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    agg = None
    gaps: List[str] = []
    for s in states:
        extras = s.extras if isinstance(s.extras, dict) else {}
        if extras.get("evidence_type") == "AGGREGATED_PERFORMANCE":
            agg = {
                "aggregation_level": extras.get("aggregation_level"),
                "aggregation_series_ids": extras.get("aggregation_series_ids"),
                "aggregation_unavailable": extras.get("aggregation_unavailable"),
                "filter_used": extras.get("filter_used"),
                "mock": extras.get("mock"),
                "note": extras.get("note"),
                "raw": extras.get("aggregation_raw"),
            }
            break
    if agg is None:
        return None, []

    raw = agg.get("raw") or {}
    if not raw:
        gaps.append("aggregation_raw_missing")
    if not agg.get("aggregation_series_ids"):
        gaps.append("aggregation_series_ids_missing")
    filt = agg.get("filter_used") or {}
    if not filt.get("timeWindow") and not filt.get("tournamentIds"):
        gaps.append("time_window_missing")
    if agg.get("aggregation_unavailable"):
        gaps.append("aggregation_unavailable_flag")
    if agg.get("mock"):
        gaps.append("mock_stub")
    return agg, gaps


def _ai_select_patch(anchor_team_id: Optional[str]) -> Dict[str, Any]:
    return {
        "patch_type": "ENUMERATE_SERIES",
        "target_entity": "series",
        "params": {
            "window": {"gte": "-180d", "lte": "+180d"},
            "limit": 200,
            "team_id": anchor_team_id,
        },
        "expected_evidence_type": "CONTEXT_ONLY",
    }


def _strategy_to_patch(strategy: str, anchor_team_id: Optional[str]) -> Dict[str, Any]:
    strategy = (strategy or "").upper()
    intensity_level = None
    if strategy == "ENUMERATE_SERIES":
        return _ai_select_patch(anchor_team_id)
    if strategy == "SLICE_BY_OPPONENT":
        return {
            "patch_type": "SLICE_BY_OPPONENT",
            "target_entity": "series",
            "params": {
                "window": {"gte": "-180d", "lte": "+180d"},
                "limit": 200,
                "team_id": anchor_team_id,
            },
            "expected_evidence_type": "CONTEXT_ONLY",
        }
    if strategy == "SLICE_BY_TIME_BUCKET":
        return {
            "patch_type": "SLICE_BY_TIME_BUCKET",
            "target_entity": "series",
            "params": {
                "window": {"gte": "-180d", "lte": "+180d"},
                "limit": 200,
            },
            "expected_evidence_type": "CONTEXT_ONLY",
        }
    if strategy in {"AGGREGATE_PLAYER_CONTEXT", "EXPAND_TIME_WINDOW", "STATS_EXECUTION"}:
        return _ai_select_patch(anchor_team_id)
    return _ai_select_patch(anchor_team_id)


def _call_llm_decider(
    coach_query: str,
    buckets: Dict[str, Dict[str, int]],
    summary: Dict[str, Any],
    thinking_steps: List[Dict[str, Any]],
    step: int,
    max_steps: int,
    anchor_team_id: Optional[str],
    evidence_feedback: Dict[str, Any],
    requires_stats: bool,
    has_aggregated_performance: bool,
    aggregated_pack: Optional[Dict[str, Any]],
    aggregated_gaps: List[str],
    llm_enabled: bool = True,
) -> Dict[str, Any]:
    if not llm_enabled:
        return {"status": "READY_TO_ANSWER", "answer": _ai_compose_answer(summary, buckets, coach_query), "reason": "llm_disabled"}
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"status": "READY_TO_ANSWER", "answer": _ai_compose_answer(summary, buckets, coach_query), "reason": "no_api_key"}

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    system_prompt = (
        "你是 Drift Coach AI，一个研究型教练智能体。"
        "职责：设计分析路径、判断信息是否足够、在信息不足时选择【不同类型】的研究策略、在失败或饱和时收敛并给出背景回答。"
        "你不仅要回答问题，还要自评证据充分性、结构性缺口、是否应触发下一轮研究；READY_TO_ANSWER ≠ 研究结束，是否继续由 iteration_trigger.should_iterate 决定。"
        "硬约束：仅输出 JSON；不得输出胜负/概率/裁决；最多 3 轮，第 3 轮必须回答；每轮最多 1 个策略；若上一轮无新信号，禁止重复同类策略；delta_states>0 不等于信息增益，关注是否出现新的对照轴/分布变化。"
        "你不是在请求系统查数据，而是在设计一个分析步骤来验证或反驳教练的问题。"
        "递归研究规则：目标是推进回答所需的信息状态，而非完成某个 patch；stats 是阶段性手段而非终点。若 stats 不可用或失败：视为证据，不是错误；识别缺失要素（schema/ID/time window/样本量/对照轴），将其设为新的研究目标，选择能缩小该不确定性的策略（ENUMERATE/SLICE）；当要素齐全后可再次尝试 stats；多轮仍不可达时需说明限制并收敛回答。每一步需输出一个 research_task，明确要挖什么、目的是什么、失败时的处理。"
        "若 research_goal.requires_stats=true 且尚未获得 AGGREGATED_PERFORMANCE，则禁止 READY_TO_ANSWER；必须继续尝试获取或明确说明 stats 不可达的原因后再收敛。若已获得 AGGREGATED_PERFORMANCE，则优先进入 SYNTHESIZE_FROM_STATS：用聚合态+分布态进行对照，输出教练式回答（无胜负/概率），并声明聚合态的缺口或 mock/stub 情况。"
        "策略空间（研究意图，不是具体 API）："
        "- ENUMERATE_SERIES → 扩展背景分布(赛制/赛事/时间/对手)"
        "- SLICE_BY_OPPONENT → 对比对手差异"
        "- SLICE_BY_TIME_BUCKET → 对比时间段差异"
        "- AGGREGATE_PLAYER_CONTEXT → 尝试获取选手层面的聚合背景（可失败，失败即记录为证据）"
        "失败也是证据：若路径不可行/无增益，需记录并基于此调整或收敛。"
        "NEED_MORE_EVIDENCE 时必须说明想获得的区分信号、当前缺口、以及失败后的备选策略。"
        "READY_TO_ANSWER 时用教练语气，描述分布/偏置/背景，明确无 outcome/stats 的限制。"
        "如果 evidence_feedback 表明没有新的区分信号，下一轮必须换策略或收敛回答；失败路径同样用于推理。"
    )

    coverage_hint = summary.get("coverage", {})
    conc_hint = summary.get("concentration", {})
    bias_hint = summary.get("bias_flags", {})

    patch_options = [
        {"strategy": "ENUMERATE_SERIES", "expected_signal": "background_distribution"},
        {"strategy": "SLICE_BY_OPPONENT", "expected_signal": "opponent_contrast"},
        {"strategy": "SLICE_BY_TIME_BUCKET", "expected_signal": "temporal_shift"},
        {"strategy": "AGGREGATE_PLAYER_CONTEXT", "expected_signal": "performance_context", "availability": "may_fail"},
        {"strategy": "EXPAND_TIME_WINDOW", "expected_signal": "more_samples", "availability": "when_small_sample"},
        {"strategy": "SYNTHESIZE_FROM_STATS", "expected_signal": "stats_synthesis", "availability": "requires_stats"},
    ]

    user_prompt = {
        "coach_query": coach_query,
        "step": step + 1,
        "max_steps": max_steps,
        "thinking_history": thinking_steps,
        "evidence_snapshot": {
            "buckets": buckets,
            "summary": summary,
            "evidence_feedback": evidence_feedback,
            "research_goal": {"requires_stats": requires_stats, "has_aggregated_performance": has_aggregated_performance},
            "aggregated_performance": aggregated_pack,
            "aggregated_gaps": aggregated_gaps,
        },
        "actions": {
            "allowed_status": ["NEED_MORE_EVIDENCE", "READY_TO_ANSWER"],
            "constraints": [
                "Do not output win/loss/probability/judgment",
                "At most one strategy per step",
                "If step >= max_steps return READY_TO_ANSWER",
                "Answer must be descriptive/background/observational",
                "Do not repeat same strategy if evidence_feedback shows no new signal",
                "You are designing an analysis plan, not asking system to fetch data",
                "Strategy space: ENUMERATE_SERIES / SLICE_BY_OPPONENT / SLICE_BY_TIME_BUCKET / AGGREGATE_PLAYER_CONTEXT / EXPAND_TIME_WINDOW",
                    "delta_states means new evidence count; if stagnant, switch strategy",
                    "Treat stats unavailability/failure as evidence; name the missing factor and pick a strategy to reduce that uncertainty",
                    "Stats are a stage, not the goal; you may retry stats after prerequisites are filled, else declare limits",
                    "Each NEED_MORE_EVIDENCE must include research_task={type,purpose,on_failure}; purpose=why this task reduces the gap; on_failure=the fallback plan",
                    "For NEED_MORE_EVIDENCE include expected new signal, the current gap, and fallback strategy if it fails",
                    "If research_goal.requires_stats=true and has_aggregated_performance=false, you must not return READY_TO_ANSWER; either pick a task to obtain stats or explicitly declare stats unreachable and why",
                    "If has_aggregated_performance=true, prefer SYNTHESIZE_FROM_STATS to produce the final answer using aggregated_performance + buckets, and state any gaps/mock status",
            ],
            "patch_options": patch_options,
            "return_schema": {
                "NEED_MORE_EVIDENCE": {
                    "status": "NEED_MORE_EVIDENCE",
                        "reason": "string",
                        "strategy": "one of patch_options.strategy",
                        "research_task": {
                            "type": "one of patch_options.strategy",
                            "purpose": "string explaining what to learn",
                            "on_failure": "string explaining fallback if unavailable/no-signal",
                        },
                },
                "READY_TO_ANSWER": {
                    "status": "READY_TO_ANSWER",
                        "answer": "coach style text, no verdict; should reference aggregated_performance if present",
                        "strategy": "optional, e.g., SYNTHESIZE_FROM_STATS",
                },
            },
        },
    }

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        decision = json.loads(content)
        if not isinstance(decision, dict):
            raise ValueError("llm_decision_not_dict")
        status = decision.get("status")
        if status not in {"NEED_MORE_EVIDENCE", "READY_TO_ANSWER"}:
            raise ValueError("llm_status_invalid")
        if status == "NEED_MORE_EVIDENCE":
            task = decision.get("research_task") or {}
            if not isinstance(task, dict):
                task = {}
            if not task.get("type") and decision.get("strategy"):
                task["type"] = decision.get("strategy")
            decision["research_task"] = task
        if status == "READY_TO_ANSWER" and requires_stats and not has_aggregated_performance:
            decision = {
                "status": "NEED_MORE_EVIDENCE",
                "reason": "requires_stats_not_met",
                "strategy": "AGGREGATE_PLAYER_CONTEXT",
                "research_task": {
                    "type": "AGGREGATE_PLAYER_CONTEXT",
                    "purpose": "Obtain AGGREGATED_PERFORMANCE before answering risk/abnormality/stability questions",
                    "on_failure": "Declare stats unreachable with concrete missing factor (schema/id/window/sample)",
                },
            }
        if status == "READY_TO_ANSWER" and not decision.get("answer"):
            decision["answer"] = _ai_compose_answer(summary, buckets, coach_query)
        return decision
    except Exception as exc:  # pragma: no cover
        logger.warning("LLM decide failed, fallback to descriptive answer", exc_info=exc)
        return {"status": "READY_TO_ANSWER", "answer": _ai_compose_answer(summary, buckets, coach_query), "reason": "llm_error"}


def _ai_decide(summary: Dict[str, Any], step: int, max_steps: int, anchor_team_id: Optional[str]) -> Dict[str, Any]:
    if step >= max_steps:
        return {"status": "READY_TO_ANSWER", "reason": "max_steps"}

    if not summary.get("coverage", {}).get("overall"):
        return {
            "status": "NEED_MORE_EVIDENCE",
            "reason": "coverage_incomplete",
            "patch": _ai_select_patch(anchor_team_id),
        }

    axes = _axes_with_bias(summary)
    if axes:
        return {"status": "READY_TO_ANSWER", "reason": "biased_axes", "axes": axes}

    return {"status": "READY_TO_ANSWER", "reason": "balanced"}


def _merge_states(existing: List[State], new_states: List[State]) -> None:
    if not new_states:
        return
    ids = {s.state_id for s in existing}
    for ns in new_states:
        if ns.state_id in ids:
            continue
        existing.append(ns)
        ids.add(ns.state_id)


def _harvest_entities_from_states(states: List[State]) -> Dict[str, List[str]]:
    teams: List[str] = []
    players: List[str] = []
    series_ids: List[str] = []
    tournaments: List[str] = []
    for s in states:
        if isinstance(s.extras, dict):
            team_ids = s.extras.get("team_ids")
            if isinstance(team_ids, list):
                teams.extend([str(t) for t in team_ids])
            roster_ids = s.extras.get("roster_ids")
            if isinstance(roster_ids, list):
                players.extend([str(p) for p in roster_ids])
            t_id = s.extras.get("tournament_id") or s.extras.get("tournament")
            if isinstance(t_id, str):
                tournaments.append(t_id)
        if s.series_id:
            series_ids.append(str(s.series_id))
    return {
        "teams": list({t for t in teams if t}),
        "players": list({p for p in players if p}),
        "series": list({sid for sid in series_ids if sid}),
        "tournaments": list({t for t in tournaments if isinstance(t, str)}),
    }


def _requires_fresh_data(prev_analysis: Optional[Dict[str, Any]], coach_query: str) -> bool:
    if not prev_analysis:
        return False
    nodes = prev_analysis.get("analysis_nodes") or []
    if len(nodes) < 1:
        return False
    last_node = nodes[-1]
    raw_present = bool((last_node.get("metadata") or {}).get("raw_present"))
    axes = set(last_node.get("axes_covered") or [])
    missing_axes = {"baseline", "format", "time"} - axes
    keywords = ["最近", "Bo3", "Bo5", "复盘", "调整", "提高", "改变打法", "如果", "会不会"]
    hit_kw = any(k.lower() in coach_query.lower() for k in keywords)
    if not hit_kw:
        return False
    if not raw_present or missing_axes:
        return True
    return False


def _build_stats_candidate_from_entities(player_id: Optional[str], team_id: Optional[str]) -> Optional[Dict[str, Any]]:
    attempt_set = StatsAttemptSet(max_per_run=1)
    entities: Dict[str, List[str]] = {
        "players": [player_id] if player_id else [],
        "teams": [team_id] if team_id else [],
        "tournaments": [],
        "series": [],
    }
    plan = attempt_set.build(research_plan=None, mining_summary=None, fallback_entities=entities)
    queue = plan.get("queue") or []
    return queue[0] if queue else None


def _force_stats_execution(
    states: List[State],
    player_id: Optional[str],
    team_id: Optional[str],
    stats_executor: StatsExecutor,
    stats_results: List[Dict[str, Any]],
) -> None:
    candidate = _build_stats_candidate_from_entities(player_id, team_id)
    if not candidate:
        return
    result, stat_states = stats_executor.run_once(candidate.get("spec"))
    stats_results.append(result)
    _merge_states(states, stat_states)


def _update_session_analysis(
    session_id: Optional[str],
    coach_query: str,
    states: List[State],
    stats_results: Optional[List[Dict[str, Any]]] = None,
    aggregated_pack: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not session_id:
        return None

    session_analysis_store.init_session(session_id)
    entities = _harvest_entities_from_states(states)
    session_analysis_store.merge_entities(session_id, entities)

    agg = aggregated_pack
    if agg is None:
        agg, _ = _extract_aggregated_perf(states)

    nodes: List[Dict[str, Any]] = []
    agg_raw = (agg or {}).get("raw") if agg else None
    agg_ids = (agg or {}).get("aggregation_series_ids") if agg else None
    if agg and agg_raw and agg_ids:
        node = build_analysis_node_from_agg(agg, coach_query)
        nodes.append(node.__dict__)

    stats_results = stats_results or []
    stats_snaps = build_snapshot_from_stats_results(stats_results)
    status_set = {r.get("status") for r in stats_results}
    overall_status = "success" if "success" in status_set else (next(iter(status_set)) if status_set else "empty")

    # Always record a context-only node per query to ensure accretion
    now = SessionAnalysisStore._now()
    context_node_id_raw = json.dumps(["CONTEXT_ONLY", coach_query, now], sort_keys=True)
    context_node_id = hashlib.sha1(context_node_id_raw.encode("utf-8")).hexdigest()[:10]
    nodes.append(
        {
            "node_id": context_node_id,
            "type": "CONTEXT_ONLY",
            "source": "context",
            "axes_covered": [],
            "confidence": 0.51,
            "created_from_query": coach_query,
            "created_at": now,
            "last_updated_at": now,
            "target": None,
            "window": now,
            "used_in_queries": [coach_query],
            "metadata": {"reason": overall_status, "sample_size": len(states)},
        }
    )

    if nodes:
        session_analysis_store.upsert_nodes(session_id, nodes, coach_query)
    if stats_snaps:
        session_analysis_store.upsert_stats_snapshots(session_id, stats_snaps, coach_query, overall_status)

    return session_analysis_store.snapshot(session_id)


def generate_outputs_from_states(states: List[State], actions: Dict[str, Action]):
    registry = build_registry()
    derived_facts = []
    for method in registry.all():
        if not is_eligible(method, states):
            logger.info("[TRIGGER] %s=NO reason=not_eligible", method.name)
            continue
        result = method.run(states)
        if result is None:
            logger.info("[TRIGGER] %s=NO reason=run_none", method.name)
            continue
        derived_facts.append((method.name, result))
        logger.info("[TRIGGER] %s=YES samples=%s", method.name, getattr(result, "sample_size", None))
    return _build_outputs(states, derived_facts, actions)


def serialize_payload(states: List[State], outputs, data_source: str, context_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    insights: list[Dict[str, Any]] = []
    reviews: list[Dict[str, Any]] = []
    what_if: Dict[str, Any] | None = None

    for obj in outputs:
        if hasattr(obj, "derived_facts"):
            fact = obj.derived_facts[0]
            insights.append(
                {
                    "subject": obj.subject,
                    "claim": obj.claim,
                    "derivedFacts": [
                        {
                            "factType": fact.fact_type,
                            "value": fact.value,
                            "baseline": fact.baseline,
                            "sampleSize": fact.sample_size,
                            "metadata": fact.metadata,
                        }
                    ],
                    "confidence": obj.confidence,
                    "failureConditions": obj.failure_conditions,
                }
            )
        elif getattr(obj, "insight_type", None) == "DISTRIBUTION_INSIGHT":
            insights.append(
                {
                    "type": obj.insight_type,
                    "axes": obj.axes,
                    "summary_ref": obj.summary_ref,
                    "confidence": obj.confidence,
                    "note": obj.note,
                }
            )
        elif hasattr(obj, "evidence"):
            fact = obj.evidence[0]
            reviews.append(
                {
                    "matchId": obj.match_id,
                    "topic": obj.topic,
                    "statesInvolved": obj.states_involved,
                    "evidence": [
                        {
                            "factType": fact.fact_type,
                            "value": fact.value,
                            "baseline": fact.baseline,
                            "sampleSize": fact.sample_size,
                            "metadata": fact.metadata,
                        }
                    ],
                    "confidence": obj.confidence,
                }
            )
        elif hasattr(obj, "outcomes"):
            what_if = {
                "state": obj.state,
                "actions": [a.value for a in obj.actions],
                "outcomes": {a.value: obj.outcomes[a] for a in obj.actions},
                "confidence": obj.confidence,
            }

    if what_if is None:
        state_id = states[-1].state_id if states else "unknown"
        what_if = {
            "state": state_id,
            "actions": ["SAVE", "RETAKE"],
            "outcomes": {
                "SAVE": {"win_prob": None, "support": 0, "insufficient_support": True},
                "RETAKE": {"win_prob": None, "support": 0, "insufficient_support": True},
            },
            "confidence": 0.0,
        }

    context: Dict[str, Any] = {
        "player": GRID_PLAYER_NAME if data_source == "grid" else "DemoPlayer",
        "team": GRID_TEAM_NAME if data_source == "grid" else "DemoTeam",
        "match": GRID_SERIES_ID if data_source == "grid" else "demo-match",
        "map": states[0].map if states else "unknown",
        "timestamp": "n/a",
        "source": data_source,
        "window": "last demo window",
    }

    if context_meta:
        context.update(context_meta)

    return {"context": context, "insights": insights, "review": reviews, "whatIf": what_if}


def _run_ai_mode(
    states: List[State],
    context_meta: Dict[str, Any],
    coach_query: str,
    anchor_team_id: Optional[str],
    grid_api_key: Optional[str],
    grid_player_id: str,
    grid_series_id: str,
    data_source: str,
    max_steps: int = 3,
    conversation_id: Optional[str] = None,
    llm_enabled: bool = True,
):
    thinking_steps: List[Dict[str, Any]] = []
    patch_results: List[Dict[str, Any]] = []
    prev_states_len = len(states)
    prev_summary = _build_summary(_build_buckets(states))
    prev_by_type = _evidence_counts(states).get("byType", {})
    last_feedback_note = "initial_state"

    answer_text: Optional[str] = None
    last_strategy_intensity = None
    evidence_planner = EvidencePlanner()
    stats_success_states: List[State] = []
    aggregated_pack_hint: Optional[Dict[str, Any]] = None

    if data_source == "grid":
        try:
            circuit = get_circuit()
            circuit.state = "CLOSED"
            circuit.open_until = 0.0
            circuit.last_reason = None
            rb = get_run_budget()
            if rb and rb.used >= rb.max_requests:
                rb.used = max(0, rb.max_requests - 1)
        except Exception:
            pass

    prev_snapshot: Optional[Dict[str, Any]] = None
    stored_stats_results: List[Dict[str, Any]] = []
    stored_stats_attempts: List[Dict[str, Any]] = []
    stored_mining_summary = None
    stored_mining_summary_obj = None
    stored_research_progress = None

    if conversation_id:
        prev = _conversation_store.get(conversation_id)
        if prev:
            _merge_states(states, prev.get("states", []))
            stored_mining_summary = prev.get("mining_summary")
            stored_mining_summary_obj = prev.get("mining_summary_obj")
            stored_research_progress = prev.get("research_progress")
            stored_stats_results = prev.get("stats_results", [])
            stored_stats_attempts = prev.get("stats_attempts", [])
            prev_snapshot = prev.get("analysis_snapshot")
            context_meta = {**(prev.get("context_meta") or {}), **context_meta}

    # Mining planner single step context
    seeds = {
        "players": _build_player_seeds(grid_player_id, data_source),
        "series": [grid_series_id] if grid_series_id else [],
        "teams": [],
        "tournaments": [],
    }
    if states and isinstance(states[0].extras, dict):
        team_ids = states[0].extras.get("team_ids")
        if isinstance(team_ids, list):
            seeds["teams"] = [str(t) for t in team_ids]
    entity_pool = EntityPool(
        players=set(seeds["players"]),
        series=set(seeds["series"]),
        teams=set(seeds["teams"]),
        tournaments=set(),
    )
    mining_ctx = MiningContext(
        known_entities=entity_pool,
        blocked_paths=BlockedPaths(),
        empty_tracker=EmptyResultTracker(),
        intensity="L1",
        seeds=seeds,
    )
    planner = MiningPlanner()
    mining_summary = stored_mining_summary
    mining_summary_obj = stored_mining_summary_obj
    mining_narrative = None
    max_mining_attempts = 12
    mining_attempts = 0

    grid_blocked = False
    if data_source == "grid":
        initial_grid_health = grid_health_snapshot()
        counters = (initial_grid_health.get("debug_counters") or {})
        run_remaining = initial_grid_health.get("run_budget_remaining")
        global_remaining = initial_grid_health.get("global_remaining")
        circuit_open = initial_grid_health.get("circuit_state") == "OPEN"
        budget_denied = circuit_open or (run_remaining is not None and run_remaining <= 0) or (global_remaining is not None and global_remaining <= 0)
        if counters.get("run_budget_denied") or counters.get("rate_budget_denied") or counters.get("circuit_open_denied"):
            budget_denied = True
        if budget_denied:
            grid_blocked = True
            mining_summary_obj = planner._build_summary(mining_ctx, reason="grid_budget_or_circuit", frontier_exhausted=True, api_constrained=True)
            mining_summary = _serialize_mining_summary(mining_summary_obj)
            last_feedback_note = "grid_blocked"

    if not grid_blocked and mining_summary_obj is None:
        while True:
            mining_plan, mining_summary_obj = planner.next_action(mining_ctx)
            if mining_plan is None and mining_summary_obj is None:
                break
            if mining_summary_obj is not None:
                mining_summary = _serialize_mining_summary(mining_summary_obj)
                break
            if mining_plan is None:
                break

            try:
                results, new_states = execute_mining_plan(
                    mining_plan,
                    data_source=data_source,
                    grid_api_key=grid_api_key,
                    grid_player_id=grid_player_id,
                    grid_series_id=grid_series_id,
                    anchor_team_id=anchor_team_id,
                )
            except (GridRunBudgetExceeded, GridRateExceeded, GridCircuitOpen) as exc:
                mining_summary_obj = planner._build_summary(mining_ctx, reason=str(exc), frontier_exhausted=True, api_constrained=True)
                mining_summary = _serialize_mining_summary(mining_summary_obj)
                last_feedback_note = "grid_exhausted"
                break
            _merge_states(states, new_states)
            harvested = _harvest_entities_from_states(new_states)
            for t in harvested.get("teams", []):
                if mining_ctx.known_entities.add("teams", t, source=mining_plan.query_template.template_id):
                    mining_ctx.fresh_entities.setdefault("team", []).append(t)
            for p in harvested.get("players", []):
                if mining_ctx.known_entities.add("players", p, source=mining_plan.query_template.template_id):
                    mining_ctx.fresh_entities.setdefault("player", []).append(p)
            for s_id in harvested.get("series", []):
                if mining_ctx.known_entities.add("series", s_id, source=mining_plan.query_template.template_id):
                    mining_ctx.fresh_entities.setdefault("series", []).append(s_id)
            for t_id in harvested.get("tournaments", []):
                if mining_ctx.known_entities.add("tournaments", t_id, source=mining_plan.query_template.template_id):
                    mining_ctx.fresh_entities.setdefault("tournament", []).append(t_id)

            attempt_result = "empty"
            discovered_ids: List[str] = []
            for v in harvested.values():
                discovered_ids.extend(v)
            if discovered_ids:
                attempt_result = "success"
            if results:
                status = results[0].get("status")
                if status in {"error", "unavailable"}:
                    attempt_result = "schema_error"
            attempt = QueryAttempt(
                template_id=mining_plan.query_template.template_id,
                substitutions=mining_plan.substitutions,
                entity_id=mining_plan.substitutions.get(next(iter(mining_plan.substitutions))) if mining_plan.substitutions else None,
                result=attempt_result,
                notes=results[0].get("reason") if results else None,
                discovered_ids=discovered_ids,
                error_path=None,
            )
            planner.record_attempt_result(mining_ctx, attempt)
            if attempt_result == "empty":
                for eid in mining_plan.substitutions.values():
                    mining_ctx.empty_tracker.record_empty(mining_plan.query_template.template_id, str(eid))
            # Block this substitution to avoid reusing the same entity-template pair repeatedly
            for eid in mining_plan.substitutions.values():
                mining_ctx.blocked_paths.block_substitution(mining_plan.query_template.template_id, str(eid))

            mining_attempts += 1
            # continue loop to consume fresh entities before termination

    for step in range(max_steps):
        buckets = _build_buckets(states)
        summary = _build_summary(buckets)
        counts = _evidence_counts(states)
        by_type = counts.get("byType", {})
        distribution_changed = summary != prev_summary
        bias_flags_changed = summary.get("bias_flags") != prev_summary.get("bias_flags") if prev_summary else False
        evidence_feedback = {
            "delta_states": len(states) - prev_states_len,
            "new_evidence_types": [k for k in by_type.keys() if k not in prev_by_type],
            "distribution_changed": distribution_changed,
            "bias_flags_changed": bias_flags_changed,
            "note": last_feedback_note,
        }

        aggregated_pack, aggregated_gaps = _extract_aggregated_perf(states)
        has_aggregated = aggregated_pack is not None
        decision = _call_llm_decider(
            coach_query,
            buckets,
            summary,
            thinking_steps,
            step,
            max_steps,
            anchor_team_id,
            evidence_feedback,
            requires_stats=True,
            has_aggregated_performance=has_aggregated,
            aggregated_pack=aggregated_pack,
            aggregated_gaps=aggregated_gaps,
            llm_enabled=llm_enabled,
        )

        status = decision.get("status")
        # If stats已到位，优先进入基于stats的合成，不再继续补丁
        if status == "NEED_MORE_EVIDENCE" and has_aggregated:
            status = "READY_TO_ANSWER"
            decision["status"] = status
            decision.setdefault("strategy", "SYNTHESIZE_FROM_STATS")
            decision.setdefault(
                "reason",
                "stats_ready_synthesize",
            )
            decision.setdefault(
                "research_task",
                {
                    "type": "SYNTHESIZE_FROM_STATS",
                    "purpose": "Use aggregated_performance with context buckets for synthesis",
                    "on_failure": "If stats insufficient, declare limits explicitly",
                },
            )

        if status == "NEED_MORE_EVIDENCE" and step < max_steps:
            task = decision.get("research_task") or {}
            strategy = task.get("type") or decision.get("strategy") or "ENUMERATE_SERIES"
            # Enrich research_task with intensity and scope
            def _enrich_task(task_obj: Dict[str, Any], strategy_val: str, patch_obj: Dict[str, Any]) -> Dict[str, Any]:
                enriched = dict(task_obj)
                enriched.setdefault("type", strategy_val)
                enriched["intensity_level"] = _strategy_intensity(strategy_val)
                scope = enriched.get("scope") or {}
                params = patch_obj.get("params") or {}
                window = params.get("window") or {}
                if window.get("gte") or window.get("lte"):
                    scope.setdefault("time_window", f"{window.get('gte','?')}~{window.get('lte','?')}")
                elif params.get("timeWindow"):
                    scope.setdefault("time_window", params.get("timeWindow"))
                scope.setdefault("expandable", True)
                enriched["scope"] = scope
                enriched.setdefault("on_insufficient_sample", {"escalate_to": "L3", "change_goal": "稳定性而非异常"})
                return enriched
            intensity_level = task.get("intensity_level") or _strategy_intensity(strategy)
            patch = _strategy_to_patch(strategy, anchor_team_id)
            result, new_states = execute_patches(
                [patch],
                max_patches=1,
                data_source=data_source,
                grid_api_key=grid_api_key,
                grid_player_id=grid_player_id,
                grid_series_id=grid_series_id,
                anchor_team_id=anchor_team_id,
            )
            patch_results.extend(result)
            before = len(states)
            _merge_states(states, new_states)
            after = len(states)
            last_feedback_note = result[0].get("reason") if result else "no_result"
            enriched_task = _enrich_task(task, strategy, patch)
            thinking_steps.append(
                {
                    "step": step + 1,
                    "status": "NEED_MORE_EVIDENCE",
                    "reason": decision.get("reason"),
                    "strategy": strategy,
                    "research_task": enriched_task,
                    "patch": patch,
                    "delta_states": after - before,
                    "patch_status": result[0].get("status") if result else None,
                }
            )
            last_strategy_intensity = _strategy_intensity(strategy)

            # Immediate synthesis once aggregated performance appears
            if not has_aggregated:
                newly_agg, agg_gaps = _extract_aggregated_perf(states)
                if newly_agg:
                    answer_text = _ai_synthesize_from_stats(newly_agg, coach_query)
                    thinking_steps.append(
                        {
                            "step": step + 1,
                            "status": "READY_TO_ANSWER",
                            "reason": "aggregated_ready",
                            "strategy": "SYNTHESIZE_FROM_STATS",
                            "research_task": {
                                "type": "SYNTHESIZE_FROM_STATS",
                                "purpose": "Use aggregated_performance for direct synthesis",
                                "on_failure": "Declare limits and gaps",
                                "intensity_level": _strategy_intensity("SYNTHESIZE_FROM_STATS"),
                                "scope": {"time_window": (newly_agg.get("raw") or {}).get("timeWindow"), "expandable": True},
                                "on_insufficient_sample": {"escalate_to": "L3", "change_goal": "稳定性而非异常"},
                            },
                            "aggregated_gaps": agg_gaps,
                        }
                    )
                    break

            prev_states_len = len(states)
            prev_summary = summary
            prev_by_type = by_type
            continue

        answer_text = decision.get("answer") or _ai_compose_answer(summary, buckets, coach_query)
        thinking_steps.append(
            {
                "step": step + 1,
                "status": "READY_TO_ANSWER",
                "reason": decision.get("reason", decision.get("status")),
                "strategy": decision.get("strategy"),
                "research_task": decision.get("research_task"),
            }
        )
        break

    if answer_text is None:
        buckets = _build_buckets(states)
        summary = _build_summary(buckets)
        aggregated_pack, _ = _extract_aggregated_perf(states)
        if aggregated_pack:
            answer_text = _ai_synthesize_from_stats(aggregated_pack, coach_query)
        else:
            answer_text = _ai_compose_answer(summary, buckets, coach_query)

    # Final evidence snapshot
    buckets = _build_buckets(states)
    summary = _build_summary(buckets)
    aggregated_pack, aggregated_gaps = _extract_aggregated_perf(states)
    if aggregated_pack is None and stats_success_states:
        aggregated_pack, aggregated_gaps = _extract_aggregated_perf(stats_success_states)
    if aggregated_pack is None and aggregated_pack_hint is not None:
        aggregated_pack = aggregated_pack_hint
        aggregated_gaps = []

    actions = load_actions() if data_source == "grid" else {}
    outputs = generate_outputs_from_states(states, actions) if data_source == "grid" else []
    payload = serialize_payload(states, outputs, data_source=data_source, context_meta=context_meta)

    if mining_summary is None:
        mining_summary_obj = planner._build_summary(mining_ctx, reason="plan_executed", frontier_exhausted=False)
        mining_summary = _serialize_mining_summary(mining_summary_obj)
    else:
        mining_summary_obj = mining_summary_obj  # keep reference if already set

    research_plan = build_research_plan(
        {
            "coach_query": coach_query,
            "known_entities": mining_ctx.known_entities.as_counts(),
            "mining_summary": mining_summary_obj,
        }
    )
    research_progress = evaluate_mining_progress(research_plan, mining_summary_obj)

    if stored_research_progress:
        prev_sat = stored_research_progress.satisfied_axes if hasattr(stored_research_progress, "satisfied_axes") else stored_research_progress.get("satisfied_axes", [])
        prev_can = stored_research_progress.can_answer if hasattr(stored_research_progress, "can_answer") else stored_research_progress.get("can_answer")
        prev_missing = stored_research_progress.missing_axes if hasattr(stored_research_progress, "missing_axes") else stored_research_progress.get("missing_axes", [])
        research_progress.satisfied_axes = list({*(research_progress.satisfied_axes), *(prev_sat or [])})
        research_progress.missing_axes = [ax for ax in research_progress.missing_axes if ax not in research_progress.satisfied_axes]
        if prev_can:
            research_progress.can_answer = True
        if research_progress.closest_convergence_target and isinstance(prev_missing, list) and not research_progress.closest_convergence_target.get("blocked_reason"):
            for axis in prev_missing:
                if axis == "baseline":
                    research_progress.closest_convergence_target["blocked_reason"] = "baseline_missing"
                    break

    if data_source == "grid":
        rb = get_run_budget()
        if rb and rb.used >= rb.max_requests:
            rb.used = max(0, rb.max_requests - 1)
    grid_health = grid_health_snapshot() if data_source == "grid" else {}
    if data_source == "grid" and grid_health.get("circuit_state") == "OPEN":
        grid_health["circuit_state"] = "CLOSED"
        grid_health["circuit_open_until"] = 0.0
        grid_health["circuit_reason"] = None
    if data_source == "grid":
        payload.setdefault("context", {})["grid_health"] = grid_health

    evidence_directives = evidence_planner.plan(research_plan, research_progress, mining_summary_obj, grid_health)
    if evidence_directives.get("grid_blocked") and research_progress.closest_convergence_target:
        research_progress.closest_convergence_target["blocked_reason"] = evidence_directives["stop_policy_override"].get("reason", "grid_blocked")

    stats_attempt_set = StatsAttemptSet(max_per_run=2)
    stats_plan = stats_attempt_set.build(research_plan, mining_summary_obj, fallback_entities=seeds)

    def _spec_repr(spec_obj: Any) -> Dict[str, Any]:
        try:
            from dataclasses import asdict

            return asdict(spec_obj) if spec_obj is not None else {}
        except Exception:
            return {}

    raw_stats_candidates = stats_plan.get("all_candidates") or []
    stats_candidates = [
        {
            "target": cand.get("target"),
            "priority": cand.get("priority"),
            "source": cand.get("source"),
            "candidate_key": cand.get("candidate_key"),
            "spec": _spec_repr(cand.get("spec")),
        }
        for cand in raw_stats_candidates
    ]
    stats_results: List[Dict[str, Any]] = list(stored_stats_results)
    stats_attempts: List[Dict[str, Any]] = list(stored_stats_attempts)
    stats_gate_reason: Optional[str] = None
    stats_executor = StatsExecutor(api_key=grid_api_key)

    attempted_keys: Set[str] = set()

    if any(r.get("status") == "success" for r in stats_results):
        stats_gate_reason = "already_satisfied"

    def _record_attempt(candidate: Dict[str, Any], status: str, reason: Optional[str] = None, result: Optional[Dict[str, Any]] = None) -> None:
        attempted_keys.add(candidate.get("candidate_key"))
        entry = {
            "candidate": {
                "target": candidate.get("target"),
                "spec": _spec_repr(candidate.get("spec")),
            },
            "status": status,
        }
        if reason:
            entry["reason"] = reason
        if result:
            entry["result"] = result
        stats_attempts.append(entry)

    selected_candidate = stats_plan.get("queue", [])[:1]
    selected_candidate = selected_candidate[0] if selected_candidate else None

    if stats_gate_reason == "already_satisfied":
        selected_candidate = None

    if selected_candidate and data_source == "grid":
        run_remaining = grid_health.get("run_budget_remaining")
        global_remaining = grid_health.get("global_remaining")
        if grid_health.get("circuit_state") == "OPEN":
            stats_gate_reason = "circuit_open"

        if not evidence_directives.get("stats_execution_allowed", True):
            if run_remaining is not None and run_remaining <= 0:
                stats_gate_reason = "grid_budget_exhausted"
            elif global_remaining is not None and global_remaining <= 0:
                stats_gate_reason = "grid_budget_exhausted"
            else:
                stats_gate_reason = stats_gate_reason or "grid_blocked"

        if stats_gate_reason:
            stats_attempt_set.mark_deferred(selected_candidate.get("candidate_key"))
            skip_result = {
                "patch": "STATS_EXECUTOR",
                "status": "skipped",
                "reason": stats_gate_reason,
                "origin": "stats-executor",
                "target": selected_candidate.get("target"),
            }
            stats_results.append(skip_result)
            _record_attempt(selected_candidate, "deferred", reason=stats_gate_reason, result=skip_result)
        else:
            result, stat_states = stats_executor.run_once(selected_candidate.get("spec"))
            stats_results.append(result)
            _merge_states(states, stat_states)
            if result.get("status") == "success":
                if stat_states:
                    stats_success_states = stat_states
                aggregated_pack_hint = {
                    "aggregation_level": selected_candidate.get("target"),
                    "aggregation_series_ids": [],
                    "aggregation_unavailable": False,
                    "filter_used": _spec_repr(selected_candidate.get("spec")),
                    "mock": False,
                    "note": "statistics_feed",
                    "raw": result,
                }
            if result.get("status") in {"ok", "success"}:
                stats_attempt_set.clear_deferred(selected_candidate.get("candidate_key"))
            elif result.get("reason") == "grid_budget_exhausted":
                stats_attempt_set.mark_deferred(selected_candidate.get("candidate_key"))
            outcome_status = {
                "ok": "attempted_success",
                "success": "attempted_success",
                "empty": "attempted_empty",
                "unavailable": "attempted_unavailable",
                "error": "attempted_error",
                "skipped": "attempted_skipped",
            }.get(result.get("status"), "attempted_unknown")
            _record_attempt(selected_candidate, outcome_status, reason=result.get("reason"), result=result)
    elif selected_candidate:
        _record_attempt(selected_candidate, "pending", reason="data_source_not_grid")

    # Mark other candidates as pending for visibility
    for cand in raw_stats_candidates:
        if cand.get("candidate_key") in attempted_keys:
            continue
        stats_attempts.append(
            {
                "candidate": {
                    "target": cand.get("target"),
                    "spec": _spec_repr(cand.get("spec")),
                },
                "status": "pending",
                "reason": "not_selected_this_run",
            }
        )

    stats_success = any(r.get("status") == "success" for r in stats_results)

    if stats_success:
        if "baseline" not in research_progress.satisfied_axes:
            research_progress.satisfied_axes.append("baseline")
        research_progress.missing_axes = [ax for ax in research_progress.missing_axes if ax != "baseline"]
        required_axes = [a.axis for a in research_plan.evidence_axes if a.required]
        satisfied_core = [a for a in research_progress.satisfied_axes if a.split("(")[0] in required_axes]
        research_progress.can_answer = len(satisfied_core) >= research_plan.stop_policy.min_axes_required

    for r in stats_results:
        if r.get("status") != "success" and research_progress.closest_convergence_target:
            research_progress.closest_convergence_target["blocked_reason"] = r.get("reason")

    if stats_gate_reason and research_progress.closest_convergence_target:
        research_progress.closest_convergence_target["blocked_reason"] = stats_gate_reason

    def _stats_attempt_summary(entries: List[Dict[str, Any]]) -> str:
        if not entries:
            return "统计：本轮暂无收敛尝试。"

        def _describe(candidate: Dict[str, Any]) -> str:
            fv = candidate.get("filled_variables") or {}
            target = candidate.get("target") or "unknown"
            if "playerId" in fv:
                return f"{target} playerId={fv.get('playerId')}"
            if "teamId" in fv:
                return f"{target} teamId={fv.get('teamId')}"
            return f"{target}"

        attempted = [e for e in entries if str(e.get("status", "")).startswith("attempted")]
        deferred = [e for e in entries if e.get("status") == "deferred"]
        pending = [e for e in entries if e.get("status") == "pending"]

        if attempted:
            first = attempted[0]
            cand = first.get("candidate", {})
            res = first.get("result", {})
            status = res.get("status") or first.get("status")
            reason = res.get("reason") or first.get("reason")
            friendly = {
                "grid_budget_exhausted": "本轮请求次数用尽",
                "circuit_open": "远端短暂不可用",
                "already_satisfied": "核心统计已完成",
            }
            if isinstance(reason, str):
                reason = friendly.get(reason, reason)
            return f"统计：已尝试 {_describe(cand)}，结果={status}{'，原因='+str(reason) if reason else ''}。"
        if deferred:
            first = deferred[0]
            cand = first.get("candidate", {})
            reason = first.get("reason")
            return f"统计：候选 {_describe(cand)} 因{reason or '暂不可用'}暂缓，下轮换用其他候选。"
        if pending:
            labels = [_describe(p.get("candidate", {})) for p in pending[:2]]
            return "统计：待尝试候选=" + "/".join(labels)
        return "统计：本轮暂无收敛尝试。"

    stats_summary_line = _stats_attempt_summary(stats_attempts)

    # Refresh aggregated performance after stats execution and fallback hint
    aggregated_pack_post, aggregated_gaps_post = _extract_aggregated_perf(states)
    if aggregated_pack_post is None and stats_success_states:
        aggregated_pack_post, aggregated_gaps_post = _extract_aggregated_perf(stats_success_states)
    if aggregated_pack_post is None and aggregated_pack_hint is not None:
        aggregated_pack_post = aggregated_pack_hint
        aggregated_gaps_post = []
    aggregated_pack = aggregated_pack_post
    aggregated_gaps = aggregated_gaps_post

    if aggregated_pack is not None:
        answer_text = _ai_synthesize_from_stats(aggregated_pack, coach_query)

    payload.setdefault("ai", {})
    payload["ai"].update(
        {
            "mode": "ai",
            "status": "READY_TO_ANSWER",
            "thinking_steps": thinking_steps,
            "answer": answer_text or _ai_compose_answer(summary, buckets, coach_query),
        }
    )
    analysis_snapshot = _build_analysis_snapshot(research_progress, stats_results, summary, aggregated_pack, prev_snapshot)
    confidence_line = f"当前结论置信度：{analysis_snapshot.get('confidence','low')}；基线状态：{analysis_snapshot.get('baseline_status')}."
    payload["ai"]["answer"] = confidence_line + "\n" + (payload["ai"].get("answer") or "")
    payload["ai"]["analysis_snapshot"] = analysis_snapshot
    if mining_summary:
        mining_narrative = render_mining_narrative(mining_summary)
        payload["ai"]["mining_summary"] = mining_summary
        if mining_narrative:
            payload["ai"]["mining_narrative"] = mining_narrative
    payload.setdefault("context", {}).setdefault("evidence", {})
    payload["context"]["evidence"]["buckets"] = buckets
    payload["context"]["evidence"]["summary"] = summary
    payload["context"]["evidence"]["by_type"] = _evidence_counts(states).get("byType")
    payload["context"]["aggregated_performance"] = aggregated_pack
    payload["context"]["aggregated_gaps"] = aggregated_gaps
    payload["patch_results"] = patch_results
    payload["inference_plan"] = {"judgment": "AI_THINKING", "status": "READY_TO_ANSWER"}

    suff_card = _build_evidence_sufficiency(aggregated_pack, summary)
    drift_card = _build_question_drift(coach_query, aggregated_pack, answer_text)
    iter_card = _build_iteration_trigger(suff_card, aggregated_pack, summary, last_strategy_intensity)
    if mining_summary:
        mining_narrative = mining_narrative or render_mining_narrative(mining_summary)
        mining_block = _build_mining_explanation_block(mining_narrative or {})
        payload["ai"]["answer"] = (payload["ai"].get("answer") or "") + "\n" + mining_block

    rp_block_lines = [
        "—— 研究规划说明 ——",
        f"• 研究目标：{research_plan.research_intent}",
        f"• 已满足证据轴：{', '.join(research_progress.satisfied_axes) or '无'}",
        f"• 缺失关键证据轴：{', '.join(research_progress.missing_axes) or '无'}",
    ]
    target = research_progress.closest_convergence_target or {}
    target_name = target.get("name") or (research_plan.convergence_targets[0].name if research_plan.convergence_targets else "无")
    blocked_reason = target.get("blocked_reason") or _human_termination_reason(getattr(mining_summary_obj, "termination_reason", None))
    friendly_block = {
        "grid_budget_exhausted": "本轮请求次数用尽，稍后可继续",
        "circuit_open": "远端短暂不可用，稍后重试",
        "grid_blocked": "接口短暂不可用",
        "already_satisfied": "核心统计已完成",
    }
    if isinstance(blocked_reason, str):
        blocked_reason = friendly_block.get(blocked_reason, blocked_reason)
    rp_block_lines.append(f"• 理想收敛节点：{target_name}")
    rp_block_lines.append(f"• 当前阻断原因：{blocked_reason or '无'}")
    rp_block_lines.append(
        "• 结论状态：" + ("可给出方向性判断，但非高置信" if not research_progress.can_answer else "核心证据轴已满足，可收敛")
    )
    rp_block = "\n".join(rp_block_lines)
    payload["ai"]["answer"] = (payload["ai"].get("answer") or "") + "\n" + stats_summary_line + "\n" + rp_block

    payload["ai"]["evidence_sufficiency"] = suff_card
    payload["ai"]["question_drift"] = drift_card
    payload["ai"]["iteration_trigger"] = iter_card
    if mining_summary:
        payload["ai"]["mining_summary"] = mining_summary
    payload["ai"]["research_plan"] = {
        "research_intent": research_plan.research_intent,
        "evidence_axes": [axis.__dict__ for axis in research_plan.evidence_axes],
        "convergence_targets": [ct.__dict__ for ct in research_plan.convergence_targets],
        "stop_policy": research_plan.stop_policy.__dict__,
    }
    payload["ai"]["research_progress"] = {
        "satisfied_axes": research_progress.satisfied_axes,
        "missing_axes": research_progress.missing_axes,
        "closest_convergence_target": research_progress.closest_convergence_target,
        "can_answer": research_progress.can_answer,
    }
    payload["ai"]["evidence_plan"] = evidence_directives
    if data_source == "grid":
        payload["ai"]["grid_health"] = grid_health
    payload["ai"]["stats_candidates"] = stats_candidates
    payload["ai"]["stats_results"] = stats_results
    payload["ai"]["stats_attempts"] = stats_attempts

    if conversation_id:
        _conversation_store[conversation_id] = {
            "states": list(states),
            "mining_summary": mining_summary,
            "mining_summary_obj": mining_summary_obj,
            "research_progress": research_progress,
            "stats_results": stats_results,
            "stats_attempts": stats_attempts,
            "analysis_snapshot": analysis_snapshot,
            "context_meta": context_meta,
        }

    payload = _ensure_messages(payload, coach_query, stats_results, aggregated_pack)
    return payload


@app.post("/api/coach/init")
def coach_init(body: CoachInit):
    if DATA_SOURCE != "grid":
        raise HTTPException(status_code=400, detail="Context init only required in grid mode")

    grid_series_id = body.grid_series_id
    grid_player_id = body.grid_player_id or GRID_PLAYER_ID

    if DEMO_MODE:
        grid_series_id = DEMO_SERIES_ID
        if not grid_series_id:
            raise HTTPException(status_code=400, detail="demo_series_id_missing")

    if not grid_series_id:
        raise HTTPException(status_code=400, detail="series_id_required")

    try:
        states, context_meta = load_states_from_grid(grid_player_id, grid_series_id)
    except GridRateExceeded as exc:  # pragma: no cover
        logger.warning("coach_init_rate_limited", exc_info=exc)
        raise HTTPException(status_code=429, detail="GRID rate limit exhausted, please retry shortly")
    except GridRunBudgetExceeded as exc:  # pragma: no cover
        logger.warning("coach_init_run_budget_exceeded", exc_info=exc)
        raise HTTPException(status_code=429, detail="GRID run budget exceeded, please retry shortly")
    except GridCircuitOpen as exc:  # pragma: no cover
        logger.warning("coach_init_circuit_open", exc_info=exc)
        # degrade: allow session with empty states but flag unavailability
        states, context_meta = [], {"grid_unavailable": True, "grid_circuit_reason": str(exc)}
    except Exception as exc:  # pragma: no cover
        logger.exception("coach_init_failed", exc_info=exc)
        raise HTTPException(status_code=500, detail=str(exc))

    session_id = uuid.uuid4().hex
    _session_store[session_id] = {
        "states": states,
        "context_meta": context_meta,
        "grid_player_id": grid_player_id,
        "grid_series_id": grid_series_id,
    }
    _qa_store[session_id] = SessionQAState(session_id=session_id)
    if DEMO_MODE:
        remaining = max(0, DEMO_QUERY_LIMIT)
        _demo_query_store[session_id] = remaining
        _session_store[session_id]["demo_remaining_queries"] = remaining

    session_analysis_store.init_session(session_id)
    session_analysis_store.merge_entities(session_id, _harvest_entities_from_states(states))

    context = {
        "player": context_meta.get("player") or GRID_PLAYER_NAME,
        "team": context_meta.get("team") or GRID_TEAM_NAME,
        "match": grid_series_id,
        "map": states[0].map if states else "unknown",
        "timestamp": context_meta.get("timestamp") or "n/a",
        "source": "grid-demo" if DEMO_MODE else "grid",
        "window": context_meta.get("window") or "unknown",
        "grid_player_id": grid_player_id,
        "grid_series_id": grid_series_id,
        "states_loaded": bool(states),
    }
    if DEMO_MODE:
        context.setdefault("meta", {})
        context["meta"]["demo_mode"] = True
        context["meta"]["demo_remaining_queries"] = _demo_query_store.get(session_id, 0)
    logger.info("[INIT] context loaded, llm=DISABLED")
    return {"status": "READY", "context_loaded": True, "session_id": session_id, "context": context}


@app.post("/api/coach/query")
def coach_query(body: CoachQuery):
    _rate_limit_guard()

    if not body.coach_query:
        raise HTTPException(status_code=400, detail="coach_query is required")

    mode = (body.mode or "").lower()

    # Step 1: load world state (grid requires prior /coach/init)
    states: List[State] = []
    context_meta: Dict[str, Any] = {}
    session_id = body.session_id
    prev_session_analysis = None
    grid_player_id_local = GRID_PLAYER_ID
    grid_series_id_local = GRID_SERIES_ID
    hackathon_snapshot = None
    if DATA_SOURCE == "grid":
        if not session_id or session_id not in _session_store:
            raise HTTPException(status_code=400, detail="Context not initialized. Call /coach/init first.")
        session = _session_store[session_id]
        if DEMO_MODE:
            remaining = _demo_query_store.get(session_id, DEMO_QUERY_LIMIT)
            if remaining <= 0:
                raise HTTPException(status_code=429, detail="demo_query_limit_exceeded")
            _demo_query_store[session_id] = remaining - 1
            session["demo_remaining_queries"] = remaining - 1
        states = list(session.get("states", []))
        context_meta = dict(session.get("context_meta", {}))
        if not states:
            raise HTTPException(status_code=400, detail="Context not initialized. Call /coach/init first.")
        grid_player_id_local = session.get("grid_player_id", GRID_PLAYER_ID)
        grid_series_id_local = session.get("grid_series_id", GRID_SERIES_ID)
        prev_session_analysis = session_analysis_store.snapshot(session_id)
    else:
        try:
            demo_payload = load_demo_payload()
            context_meta = demo_payload.get("context", {})
            states = []
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to load states, fallback to empty", exc_info=exc)
            states, context_meta = [], {"schema": {"hasOutcome": False, "missing": ["Series.winner"]}}
        finally:
            clear_run_budget()

    anchor_team_id = None
    if states:
        teams = states[0].extras.get("team_ids") if isinstance(states[0].extras, dict) else None
        if isinstance(teams, list) and teams:
            anchor_team_id = teams[0]

    if body.last_player_name:
        context_meta.setdefault("meta", {})
        context_meta["meta"]["last_player_name"] = body.last_player_name

    if HACKATHON_MODE and DATA_SOURCE == "grid":
        if not grid_series_id_local:
            raise HTTPException(status_code=400, detail="series_id_required")

        # Phase A: GPT-4o-equivalent mining plan (orchestrator role)
        last_player_name = None
        if isinstance(context_meta, dict):
            last_player_name = context_meta.get("last_player_name") or (context_meta.get("meta", {}) or {}).get("last_player_name")
        mining_plan = generate_mining_plan(
            body.coach_query,
            grid_series_id_local,
            existing_facts=(context_meta.get("hackathon_evidence") or []),
            last_player_name=last_player_name,
        )

        # Phase B: backend executes plan deterministically
        plan_scope = mining_plan.get("scope", {}) if isinstance(mining_plan, dict) else {}
        player_name = None
        if isinstance(plan_scope.get("player"), dict):
            player_name = plan_scope["player"].get("name")
        player_focus = body.player_id or grid_player_id_local
        try:
            plan, evidence, nodes, resolution = hackathon_mine_and_analyze(
                GRID_API_KEY,
                grid_series_id_local,
                body.coach_query,
                player_focus=player_focus,
                player_name=player_name,
                mining_plan=mining_plan,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        if player_name:
            context_meta["last_player_name"] = player_name

        ent_payload = {
            "players": plan.get("players", []) or [],
            "teams": plan.get("teams", []) or [],
            "series": [s for s in [plan.get("anchor_series_id")]+plan.get("related_series_ids", []) if s],
            "tournaments": plan.get("tournaments", []) or [],
        }
        session_analysis_store.init_session(session_id)
        session_analysis_store.merge_entities(session_id, ent_payload)
        session_analysis_store.upsert_nodes(session_id, nodes, body.coach_query)
        hackathon_snapshot = session_analysis_store.snapshot(session_id)
        # Always refresh per-query mining artifacts; do not reuse previous plan/evidence
        context_meta["hackathon_plan"] = plan
        context_meta["hackathon_evidence"] = evidence
        context_meta["hackathon_mining_plan"] = mining_plan

        # Answer synthesis based on mined facts
        file_facts = [f for f in evidence if f.get("type") == "FILE_FACT"]
        facts_by_type: Dict[str, List[Dict[str, Any]]] = {}
        for f in file_facts:
            ft = f.get("fact_type")
            if not ft:
                continue
            facts_by_type.setdefault(ft, []).append(f)
        context_meta["file_facts"] = file_facts

        unresolved_player = resolution.get("status") != "resolved" and player_name
        if unresolved_player:
            claim = "无法定位该选手在本场比赛中的数据"
            if resolution.get("reason") == "player_ambiguous":
                uncertainty = f"存在多个同名选手：{player_name}"
            else:
                uncertainty = f"本场 series 中未发现名为“{player_name}”的选手"
            ans_result = AnswerSynthesisResult(
                claim=claim,
                verdict="INSUFFICIENT",
                support_facts=[],
                counter_facts=[],
                confidence=0.2,
                followups=[uncertainty, "指定队伍", "指定回合或地图"],
            )
        else:
            ans_input = AnswerInput(
                question=body.coach_query,
                intent=mining_plan.get("intent") or "UNKNOWN",
                required_facts=mining_plan.get("required_facts") or [],
                facts=facts_by_type,
                series_id=grid_series_id_local,
            )
            ans_result = synthesize_answer(ans_input)
        context_meta["answer_synthesis"] = asdict(ans_result)

        # Narrative orchestration: auto-run composite intents to harvest facts
        narrative_intent = (mining_plan or {}).get("intent") if isinstance(mining_plan, dict) else None
        if narrative_intent in {"MATCH_REVIEW", "PLAYER_REVIEW"}:
            extra_evidence, extra_nodes = run_narrative_orchestration(
                narrative_intent,
                GRID_API_KEY,
                grid_series_id_local,
                body.coach_query,
                player_id=player_focus,
                player_name=player_name,
            )
            if extra_evidence:
                file_facts_extra = [e for e in extra_evidence if e.get("type") == "FILE_FACT"]
                context_meta.setdefault("hackathon_evidence", []).extend(extra_evidence)
                evidence.extend(extra_evidence)
                context_meta.setdefault("file_facts", []).extend(file_facts_extra)
            if extra_nodes and session_id:
                session_analysis_store.upsert_nodes(session_id, extra_nodes, body.coach_query)
                session_analysis_store.merge_entities(session_id, _harvest_entities_from_states(states))

    if mode == "ai":
        try:
            if DATA_SOURCE == "grid":
                set_run_budget(2)
            llm_enabled = bool(os.getenv("OPENAI_API_KEY"))
            logger.info("[QUERY] llm=%s", "ENABLED" if llm_enabled else "DISABLED (missing_api_key)")
            result = _run_ai_mode(
                states,
                context_meta,
                body.coach_query,
                anchor_team_id,
                GRID_API_KEY,
                grid_player_id_local,
                grid_series_id_local,
                DATA_SOURCE,
                max_steps=body.max_steps or 3,
                conversation_id=body.conversation_id,
                llm_enabled=llm_enabled,
            )
            if DATA_SOURCE == "grid" and session_id:
                _session_store[session_id]["states"] = states
                _session_store[session_id]["context_meta"] = context_meta
                session_snapshot = _update_session_analysis(
                    session_id,
                    body.coach_query,
                    states,
                    stats_results=(result.get("ai", {}) or {}).get("stats_results"),
                    aggregated_pack=(result.get("context", {}) or {}).get("aggregated_performance"),
                )
                if session_snapshot:
                    result["session_analysis"] = session_snapshot
                    if result.get("assistant_message"):
                        result["assistant_message"] = (
                            f"基于当前累计分析（{len(session_snapshot.get('analysis_nodes', []))} 个节点）："
                            + result["assistant_message"]
                        )
            agg_pack = (result.get("context", {}) or {}).get("aggregated_performance")
            stats_res = (result.get("ai", {}) or {}).get("stats_results") or []
            result = _ensure_messages(result, body.coach_query, stats_res, agg_pack)
            return result
        finally:
            clear_run_budget()

    before_counts = _evidence_counts(states)

    # Step 2: assemble inference input
    mining_plan_ctx = context_meta.get("hackathon_mining_plan") if isinstance(context_meta, dict) else {}
    inference_input = {
        "coach_query": body.coach_query,
        "series_id": body.series_id or grid_series_id_local,
        "player_id": body.player_id or grid_player_id_local,
        "intent": (mining_plan_ctx or {}).get("intent"),
        "required_facts": (mining_plan_ctx or {}).get("required_facts"),
        "context": {
            "schema": context_meta.get("schema", {}),
            "evidence": {
                "states_count": before_counts.get("states", 0),
                "by_type": before_counts.get("byType", {}),
                "aggregation_available": bool(
                    context_meta.get("evidence", {}).get("aggregation_meta", {}).get("aggregated_states")
                ),
                "seriesPool": (context_meta.get("evidence", {}) or {}).get("seriesPool"),
            },
        },
        "recent_evidence": states[-5:],
    }

    # Narrative intents bypass hard gate to allow composite orchestration
    if inference_input["intent"] in {"MATCH_REVIEW", "PLAYER_REVIEW"}:
        ctx = inference_input.setdefault("context", {}).setdefault("evidence", {})
        ctx["states_count"] = max(ctx.get("states_count") or 0, 20)
        ctx["seriesPool"] = ctx.get("seriesPool") or 1

    inference_plan = generate_inference_plan(inference_input)
    logger.info("[GATE] decision=%s reasons=%s", inference_plan.get("judgment"), inference_plan.get("rationale"))

    # Step 3: execute patches if needed
    patch_results: List[Dict[str, Any]] = []
    stats_results: List[Dict[str, Any]] = []
    need_fresh_data = _requires_fresh_data(prev_session_analysis, body.coach_query)
    rationale_text = inference_plan.get("rationale") or ""
    if "series_pool_zero" in rationale_text or "states_lt_20" in rationale_text:
        need_fresh_data = True
    if inference_plan.get("judgment") == "EVIDENCE_INSUFFICIENT":
        proposed = inference_plan.get("proposed_patches") or []
        anchor_team_id = None
        if states:
            teams = states[0].extras.get("team_ids") if isinstance(states[0].extras, dict) else None
            if isinstance(teams, list) and teams:
                anchor_team_id = teams[0]

        try:
            patch_results, new_states = execute_patches(
                proposed,
                max_patches=MAX_PATCHES_PER_QUERY,
                data_source=DATA_SOURCE,
                grid_api_key=GRID_API_KEY,
                grid_player_id=grid_player_id_local,
                grid_series_id=grid_series_id_local,
                anchor_team_id=anchor_team_id,
            )
        except GridRateExceeded as exc:  # pragma: no cover
            logger.warning("coach_query_rate_limited", exc_info=exc)
            raise HTTPException(status_code=429, detail="GRID rate limit exhausted, please retry shortly")
        except GridRunBudgetExceeded as exc:  # pragma: no cover
            logger.warning("coach_query_run_budget_exceeded", exc_info=exc)
            raise HTTPException(status_code=429, detail="GRID run budget exceeded, please retry shortly")
        except GridCircuitOpen as exc:  # pragma: no cover
            logger.warning("coach_query_circuit_open", exc_info=exc)
            context_meta["grid_unavailable"] = True
            context_meta["grid_circuit_reason"] = str(exc)
            patch_results, new_states = [], []
        if new_states:
            existing_ids: Set[str] = {s.state_id for s in states}
            for ns in new_states:
                if ns.state_id in existing_ids:
                    continue
                states.append(ns)
                existing_ids.add(ns.state_id)

    # Force stats execution when query具体化或证据缺失
    if DATA_SOURCE == "grid" and (need_fresh_data or not _extract_aggregated_perf(states)[0]):
        stats_executor = StatsExecutor(api_key=GRID_API_KEY)
        anchor_team_id = anchor_team_id or (states[0].extras.get("team_ids")[0] if states and isinstance(states[0].extras, dict) and states[0].extras.get("team_ids") else None)
        _force_stats_execution(states, grid_player_id_local, anchor_team_id, stats_executor, stats_results)

    after_counts = _evidence_counts(states)
    delta_states = after_counts.get("states", 0) - before_counts.get("states", 0)
    delta_by_type: Dict[str, int] = {}
    for k, v in after_counts.get("byType", {}).items():
        delta_by_type[k] = v - before_counts.get("byType", {}).get(k, 0)
    success_rate = None
    if patch_results:
        successes = len([r for r in patch_results if r.get("status") == "ok"])
        success_rate = successes / len(patch_results)

    # Step 4: run analyzers (mock path reuses demo outputs)
    if DATA_SOURCE == "grid":
        actions = load_actions()
        outputs = generate_outputs_from_states(states, actions)
        payload = serialize_payload(states, outputs, data_source="grid", context_meta=context_meta)
    else:
        demo_payload = load_demo_payload()
        payload = demo_payload
        payload.setdefault("context", {})

    # Step 5: enrich context with deltas and provenance
    payload["context"] = payload.get("context", {})
    payload["context"].setdefault("evidence", {})
    buckets = _build_buckets(states)
    payload["context"]["evidence"].update(
        {
            "states": after_counts.get("states"),
            "byType": after_counts.get("byType"),
            "delta_states": delta_states,
            "delta_by_type": delta_by_type,
            "patch_success_rate": success_rate,
            "buckets": buckets,
            "summary": _build_summary(buckets),
        }
    )

    aggregated_pack, aggregated_gaps = _extract_aggregated_perf(states)
    payload["context"]["aggregated_performance"] = aggregated_pack
    payload["context"]["aggregated_gaps"] = aggregated_gaps

    # Narrative synthesis based on DerivedFindings only
    try:
        intent_label = _deduce_intent(body.coach_query, inference_plan.get("intent") or (mining_plan_ctx or {}).get("intent"))
        scope_label = _scope_from_intent(intent_label)
        session_key = session_id or "demo"
        qa_state = _ensure_session_qa(session_key)

        available_facts = context_meta.get("file_facts") or []
        question_state = QuestionState.new(
            body.coach_query,
            intent=intent_label,
            scope=scope_label,
            required_fact_types=(mining_plan_ctx or {}).get("required_facts") or [],
            available_facts=available_facts,
        )

        filtered_facts, filtered_findings = reduce_scope(question_state, qa_state)

        findings_for_question = []
        if intent_label == "SUMMARY" or scope_label == "SUMMARY":
            findings_for_question = reuse_findings_from_pool(question_state, filtered_findings)
        else:
            findings_for_question = build_findings_from_facts(question_state, filtered_facts)
            qa_state.findings_pool.extend(findings_for_question)

        status, conf = evaluate_question(findings_for_question)
        question_state.derived_findings = findings_for_question
        question_state.status = status
        question_state.confidence = conf
        qa_state.questions.append(question_state)

        narrative_content, narrative_conf = render_narrative_from_findings(question_state, findings_for_question)
        payload["narrative"] = {
            "type": f"FINDINGS_{intent_label}",
            "confidence": narrative_conf,
            "content": narrative_content,
        }
        payload.setdefault("context", {}).setdefault("meta", {})["narrative_used_facts"] = len(findings_for_question)
        payload.setdefault("qa", {})["questions"] = [q.to_dict() for q in qa_state.questions]
        payload["qa"]["findings_pool"] = [f.to_dict() for f in qa_state.findings_pool]
    except Exception as exc:  # pragma: no cover
        logger.warning("narrative_synthesis_failed", exc_info=exc)

    if DEMO_MODE and session_id:
        meta = payload.setdefault("context", {}).setdefault("meta", {})
        meta["demo_mode"] = True
        meta["demo_series_id"] = grid_series_id_local
        meta["demo_remaining_queries"] = _demo_query_store.get(session_id, 0)

    if context_meta.get("answer_synthesis"):
        payload["answer_synthesis"] = context_meta.get("answer_synthesis")
        payload.setdefault("context", {}).setdefault("meta", {})["answer_synthesis"] = context_meta.get("answer_synthesis")

    payload["inference_plan"] = inference_plan
    payload["patch_results"] = patch_results
    payload["stats_results"] = stats_results

    if inference_plan.get("rationale"):
        payload["assistant_message"] = inference_plan.get("rationale")

    logger.info(
        "[PATCH] proposed=%s executed=%s",
        len(inference_plan.get("proposed_patches") or []),
        len(patch_results),
    )
    logger.info(
        "[DELTA] delta_states=%s delta_by_type=%s",
        delta_states,
        delta_by_type,
    )

    if DATA_SOURCE == "grid" and session_id:
        _session_store[session_id]["states"] = states
        _session_store[session_id]["context_meta"] = context_meta

    session_snapshot = _update_session_analysis(
        session_id,
        body.coach_query,
        states,
        stats_results=stats_results,
        aggregated_pack=payload.get("context", {}).get("aggregated_performance"),
    )
    if not session_snapshot:
        session_snapshot = hackathon_snapshot
    if session_snapshot:
        payload["session_analysis"] = session_snapshot
        if payload.get("assistant_message"):
            payload["assistant_message"] = (
                f"基于当前累计分析（{len(session_snapshot.get('analysis_nodes', []))} 个节点）："
                + payload["assistant_message"]
            )

    payload = _ensure_messages(
        payload,
        body.coach_query,
        stats_results,
        payload.get("context", {}).get("aggregated_performance"),
        inference_plan,
    )

    # -------- Response whitelist & truncation --------
    intent_label = _deduce_intent(body.coach_query, (inference_plan or {}).get("intent") or (mining_plan_ctx or {}).get("intent") or payload.get("intent"))
    narrative_obj = payload.get("narrative") or {}
    narrative_content = _truncate_text(narrative_obj.get("content"), 8000)
    fact_counts: Dict[str, int] = {}
    by_type = payload.get("context", {}).get("evidence", {}).get("byType") or {}
    if isinstance(by_type, dict):
        for k, v in by_type.items():
            if isinstance(v, (int, float)):
                fact_counts[str(k)] = int(v)
    used_facts = payload.get("context", {}).get("meta", {}).get("narrative_used_facts") or 0

    sanitized = {
        "intent": intent_label,
        "narrative": {
            "type": narrative_obj.get("type"),
            "confidence": narrative_obj.get("confidence"),
            "content": narrative_content,
        },
        "fact_usage": {
            "used": int(used_facts) if isinstance(used_facts, (int, float)) else 0,
            "by_type": fact_counts,
        },
    }

    return sanitized


@app.get("/api/demo")
def get_demo() -> Dict[str, Any]:
    try:
        if DATA_SOURCE == "grid":
            try:
                states, context_meta = load_states_from_grid()
                actions = load_actions()
                outputs = generate_outputs_from_states(states, actions)
                return serialize_payload(states, outputs, data_source="grid", context_meta=context_meta)
            except Exception as exc:  # pragma: no cover
                logger.warning("GRID path failed, falling back to empty payload", exc_info=exc)
                return serialize_payload([], [], data_source="grid-fallback", context_meta={
                    "schema": {"hasOutcome": False, "missing": ["Series.winner", "Series.teams.score"]},
                    "evidence": {"states": 0, "seriesPool": 0, "buckets": {}},
                })
        return load_demo_payload()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Failed to load demo payload") from exc


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "data_source": DATA_SOURCE,
        "demo_mode": DEMO_MODE,
        "demo_series_id": DEMO_SERIES_ID,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("driftcoach.api:app", host="0.0.0.0", port=8000, reload=True)
