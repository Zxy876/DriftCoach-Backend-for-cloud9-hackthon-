import hashlib
import json
import os
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

from driftcoach.session.analysis_store import SessionAnalysisStore
from driftcoach.adapters.grid.file_download_client import load_series_events
from driftcoach.analysis.file_facts import compress_events_to_facts
from driftcoach.analysis.player_resolver import resolve_player_id
from driftcoach.analysis.fact_nodes import nodes_from_facts

SERIES_STATE_ENDPOINT = os.getenv(
    "SERIES_STATE_URL", "https://api-op.grid.gg/series-state/graphql"
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def fetch_series_state(api_key: Optional[str], series_id: str) -> Dict[str, Any]:
    if not api_key:
        return {}
    query = """
    query SeriesState($seriesId: ID!) {
      series(id: $seriesId) {
        id
        format
        startTimeScheduled
        teams {
          id
          name
          won
          players {
            id
            name
            kills
            deaths
          }
        }
        games {
          sequenceNumber
          teams {
            id
            won
            players {
              id
              kills
              deaths
            }
          }
        }
      }
    }
    """
    headers = {"Content-Type": "application/json"}
    headers["x-api-key"] = api_key
    try:
        resp = requests.post(
            SERIES_STATE_ENDPOINT,
            json={"query": query, "variables": {"seriesId": series_id}},
            headers=headers,
            timeout=float(os.getenv("SERIES_STATE_TIMEOUT", "15")),
        )
        resp.raise_for_status()
        data = resp.json()
        series = (data.get("data") or {}).get("series") or {}
        missing: List[str] = []
        for field in ["id", "format", "startTimeScheduled", "teams", "games"]:
            if field not in series or series.get(field) is None:
                missing.append(field)
        if missing:
            series["schema_missing"] = missing
        return series
    except Exception:
        return {"schema_missing": ["network_error"]}


def build_mining_plan(series_state: Dict[str, Any], anchor_series_id: str) -> Dict[str, Any]:
    if not anchor_series_id:
        raise ValueError("anchor_series_id is required for mining plan")
    games = series_state.get("games") or []
    teams = series_state.get("teams") or []
    players: List[str] = []
    for t in teams:
        for p in t.get("players") or []:
            pid = p.get("id")
            if pid:
                players.append(str(pid))
    formats = [series_state.get("format")] if series_state.get("format") else []
    return {
        "anchor_series_id": anchor_series_id,
        "related_series_ids": [str(anchor_series_id)],
        "teams": [t.get("id") for t in teams if t.get("id")],
        "players": list(dict.fromkeys(players)),
        "formats": formats,
        "tournaments": [],
        "time_buckets": [],
        "data_sources_used": ["series_state", "file_download"],
        "games_present": len(games),
    }


def extract_evidence(series_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidences: List[Dict[str, Any]] = []
    games = series_state.get("games") or []
    teams = series_state.get("teams") or []
    series_id = series_state.get("id") or "unknown"
    series_format = series_state.get("format")

    winner_team_id = None
    winners = [t for t in teams if t.get("won") is True]
    if winners:
        winner_team_id = winners[0].get("id") or winners[0].get("name")

    evidences.append(
        {
            "type": "SERIES_OUTCOME",
            "series_id": series_id,
            "winner_team_id": winner_team_id,
            "games_played": len(games),
            "format": series_format,
            "schema_missing": series_state.get("schema_missing", []),
        }
    )

    for g in games:
        seq = g.get("sequenceNumber")
        g_teams = g.get("teams") or []
        g_winners = [t for t in g_teams if t.get("won") is True]
        winning_team_id = g_winners[0].get("id") if g_winners else None
        evidences.append(
            {
                "type": "GAME_LEVEL_EVENTS",
                "game_number": seq,
                "winning_team_id": winning_team_id,
                "reversed": None,
            }
        )
        for t in g_teams:
            for p in t.get("players") or []:
                evidences.append(
                    {
                        "type": "PLAYER_PARTICIPATION",
                        "player": p.get("id") or p.get("name"),
                        "team": t.get("id"),
                        "game_number": seq,
                        "kills": p.get("kills"),
                        "deaths": p.get("deaths"),
                    }
                )

    return evidences


def _node_id(payload: List[Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def nodes_from_evidence(evidence: List[Dict[str, Any]], query: str, player_focus: Optional[str] = None) -> List[Dict[str, Any]]:
    now = SessionAnalysisStore._now()
    nodes: List[Dict[str, Any]] = []

    outcome = next((e for e in evidence if e.get("type") == "SERIES_OUTCOME"), None)
    game_events = [e for e in evidence if e.get("type") == "GAME_LEVEL_EVENTS"]
    participation = [e for e in evidence if e.get("type") == "PLAYER_PARTICIPATION"]

    games_count = len({e.get("game_number") for e in game_events if e.get("game_number") is not None})
    sample_size = games_count or (outcome.get("games_played") if outcome else 0)
    series_count = 1 if outcome else 0

    nodes.append(
        {
            "node_id": _node_id(["SERIES_SAMPLE", sample_size]),
            "type": "SERIES_SAMPLE",
            "source": "series_state",
            "axes_covered": ["series"],
            "confidence": 0.6 if sample_size >= 2 else 0.45,
            "created_from_query": query,
            "created_at": now,
            "last_updated_at": now,
            "target": None,
            "window": None,
            "used_in_queries": [query],
            "metadata": {"sample_size": sample_size, "series_count": series_count},
        }
    )

    fmt = outcome.get("format") if outcome else None
    nodes.append(
        {
            "node_id": _node_id(["FORMAT_DEPENDENCY", fmt or "unknown", sample_size]),
            "type": "FORMAT_DEPENDENCY",
            "source": "series_state",
            "axes_covered": ["format"],
            "confidence": 0.5,
            "created_from_query": query,
            "created_at": now,
            "last_updated_at": now,
            "target": None,
            "window": None,
            "used_in_queries": [query],
            "metadata": {"format": fmt or "unknown", "series_count": series_count},
        }
    )

    if participation:
        for p in participation:
            target_pid = p.get("player")
            if player_focus and target_pid and target_pid != player_focus:
                continue
            nodes.append(
                {
                    "node_id": _node_id(["PLAYER_PARTICIPATION", target_pid, p.get("game_number")]),
                    "type": "PLAYER_PARTICIPATION",
                    "source": "series_state",
                    "axes_covered": ["player"],
                    "confidence": 0.6,
                    "created_from_query": query,
                    "created_at": now,
                    "last_updated_at": now,
                    "target": target_pid,
                    "window": None,
                    "used_in_queries": [query],
                    "metadata": {
                        "games": 1,
                        "kills": p.get("kills"),
                        "deaths": p.get("deaths"),
                        "series": 1,
                    },
                }
            )
    else:
        nodes.append(
            {
                "node_id": _node_id(["PLAYER_PARTICIPATION", "unavailable", sample_size]),
                "type": "PLAYER_PARTICIPATION",
                "source": "series_state",
                "axes_covered": ["player"],
                "confidence": 0.35,
                "created_from_query": query,
                "created_at": now,
                "last_updated_at": now,
                "target": None,
                "window": None,
                "used_in_queries": [query],
                "metadata": {"available": False},
            }
        )

    wins = 1 if outcome and outcome.get("winner_team_id") else 0
    losses = 0 if wins else 0
    nodes.append(
        {
            "node_id": _node_id(["OUTCOME_PATTERN", wins, losses, sample_size]),
            "type": "OUTCOME_PATTERN",
            "source": "series_state",
            "axes_covered": ["outcome"],
            "confidence": 0.55 if sample_size >= 2 else 0.45,
            "created_from_query": query,
            "created_at": now,
            "last_updated_at": now,
            "target": None,
            "window": None,
            "used_in_queries": [query],
            "metadata": {"wins": wins, "losses": losses, "games": sample_size},
        }
    )

    max_games = None
    if fmt:
        if "5" in fmt:
            max_games = 5
        elif "3" in fmt:
            max_games = 3
    risk_meta = {
        "format": fmt or "unknown",
        "games_played": sample_size,
        "full_length": bool(max_games and sample_size >= max_games),
        "max_games": max_games,
    }
    nodes.append(
        {
            "node_id": _node_id(["RISK_PROFILE", sample_size, fmt or "unknown"]),
            "type": "RISK_PROFILE",
            "source": "series_state",
            "axes_covered": ["series"],
            "confidence": 0.55 if sample_size else 0.4,
            "created_from_query": query,
            "created_at": now,
            "last_updated_at": now,
            "target": None,
            "window": None,
            "used_in_queries": [query],
            "metadata": risk_meta,
        }
    )

    if sample_size == 0:
        nodes.append(
            {
                "node_id": _node_id(["CONTEXT_ONLY", query, "no_games"]),
                "type": "CONTEXT_ONLY",
                "source": "series_state",
                "axes_covered": ["context"],
                "confidence": 0.35,
                "created_from_query": query,
                "created_at": now,
                "last_updated_at": now,
                "target": None,
                "window": None,
                "used_in_queries": [query],
                "metadata": {"note": "无比赛事件，仅赛程与对阵结构"},
            }
        )

    if not evidence:
        nodes.append(
            {
                "node_id": _node_id(["CONTEXT_ONLY", query]),
                "type": "CONTEXT_ONLY",
                "source": "series_state",
                "axes_covered": ["context"],
                "confidence": 0.4,
                "created_from_query": query,
                "created_at": now,
                "last_updated_at": now,
                "target": None,
                "window": None,
                "used_in_queries": [query],
                "metadata": {"note": "仅基于赛程与对阵结构"},
            }
        )

    return nodes


def hackathon_mine_and_analyze(
    api_key: Optional[str],
    series_id: str,
    coach_query: str,
    player_focus: Optional[str] = None,
    player_name: Optional[str] = None,
    mining_plan: Optional[Dict[str, Any]] = None,
    should_force_fd: bool = False,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    if not series_id:
        raise ValueError("series_id is required for mining")
    series_state = fetch_series_state(api_key, series_id)
    plan = build_mining_plan(series_state, series_id)

    # Step 1: load events (must precede player resolution)
    intent_label = mining_plan.get("intent") if isinstance(mining_plan, dict) else None
    req_facts = (mining_plan.get("required_facts") or []) if isinstance(mining_plan, dict) else []
    should_force_fd = should_force_fd or any(str(f).endswith("_ROUND") or str(f).endswith("_SEQUENCE") for f in req_facts)
    logger.info(
        "[FILE_DOWNLOAD] triggered_by=NL_INTENT intent=%s required_facts=%s should_force_fd=%s",
        intent_label,
        req_facts,
        should_force_fd,
    )
    fd_result = load_series_events(series_id, api_key=api_key)
    logger.info(
        "[FILE_DOWNLOAD] events_loaded=%s source=%s reason=%s",
        len(fd_result.events),
        (fd_result.meta or {}).get("source"),
        (fd_result.meta or {}).get("reason"),
    )
    events = fd_result.events

    # Step 2: resolve player_id within series
    resolved_player_id, resolve_reason = resolve_player_id(events, player_name, series_state=series_state)
    plan.setdefault("scope", {})["player_id"] = resolved_player_id
    resolution = {
        "status": "resolved" if resolved_player_id else "unresolved",
        "reason": resolve_reason,
        "player_name": player_name,
    }
    if resolved_player_id:
        player_focus = resolved_player_id

    # Series state evidence/nodes (after resolution so we can filter)
    evidence = extract_evidence(series_state)
    nodes = nodes_from_evidence(evidence, coach_query, player_focus=player_focus)

    if fd_result.meta:
        evidence.append({"type": "FILE_DOWNLOAD_META", **fd_result.meta})

    # Step 3: facts (filtered by requested types)
    facts = compress_events_to_facts(series_id, events)
    if mining_plan:
        req = [r for r in mining_plan.get("required_facts") or [] if r != "CONTEXT_ONLY"]
        if req:
            facts = [f for f in facts if f.get("fact_type") in req]
    if resolved_player_id and player_name:
        for f in facts:
            f.setdefault("player_id", resolved_player_id)
            f.setdefault("player_name", player_name)
            if "round" not in f and f.get("round_range"):
                rr = f.get("round_range")
                if isinstance(rr, list) and len(rr) == 2:
                    f["round"] = rr[0]
            if "game" not in f and f.get("game_index") is not None:
                f["game"] = f.get("game_index")
    if facts:
        evidence.extend([{**f, "type": "FILE_FACT"} for f in facts])
    fact_nodes = nodes_from_facts(facts, coach_query)
    nodes.extend(fact_nodes)

    return plan, evidence, nodes, resolution
