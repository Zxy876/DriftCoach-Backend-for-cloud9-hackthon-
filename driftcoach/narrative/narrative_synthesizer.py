from __future__ import annotations

import pathlib
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from .narrative_types import NarrativeInput, NarrativeResult, NarrativeType
from .narrative_refinement import refine_narrative

_TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent / "templates"

SECTION_FACT_TOP_K = 1


def _load_template(name: str) -> str:
    path = _TEMPLATE_DIR / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _normalize_fact(f: Dict[str, Any]) -> Dict[str, Any]:
    scope = f.get("scope") or {}
    scope = {
        "series_id": scope.get("series_id") or f.get("series_id"),
        "game_id": scope.get("game_id") or f.get("game") or f.get("game_index"),
        "round_range": scope.get("round_range") or f.get("round_range"),
        "team_id": scope.get("team_id") or f.get("team_id"),
        "player_id": scope.get("player_id") or f.get("player_id"),
        "player_name": scope.get("player_name") or f.get("player_name"),
        "map": scope.get("map") or f.get("map"),
    }
    evidence = f.get("evidence") or {}
    sample_size = evidence.get("sample_size") or f.get("sample_size")
    if not sample_size and f.get("evidence_events"):
        sample_size = len(f.get("evidence_events"))
    metrics = f.get("metrics") or {}
    # Fallback: derive simple metrics when missing
    if not metrics:
        for key in ["loss_rate", "rounds_lost", "death_without_kast", "late_execute_rounds", "force_buy_rounds", "eco_loss_rounds"]:
            if key in f and isinstance(f.get(key), (int, float)):
                metrics[key] = f.get(key)
        if sample_size:
            metrics["sample_size"] = sample_size
    return {
        "fact_type": f.get("fact_type") or f.get("type") or "UNKNOWN",
        "scope": scope,
        "metrics": metrics,
        "note": f.get("note") or f.get("description") or "",
        "evidence": {
            "sample_size": sample_size or metrics.get("sample_size") or 0,
            "source": evidence.get("source") or f.get("derived_from") or "file_download",
        },
    }


def _format_datapoint(f: Dict[str, Any]) -> str:
    metrics = f.get("metrics") or {}
    note = f.get("note") or ""
    if metrics:
        parts = []
        for k, v in metrics.items():
            if k == "sample_size":
                continue
            if isinstance(v, float):
                parts.append(f"{k}: {v:.2f}")
            else:
                parts.append(f"{k}: {v}")
        metric_text = ", ".join(parts)
        return f"- {note or f.get('fact_type')}: {metric_text} (n={metrics.get('sample_size') or f.get('evidence', {}).get('sample_size')})"
    return f"- {note or f.get('fact_type') or '暂无明确证据'}"


def _ensure_non_empty_block(lines: List[str], placeholder: str) -> str:
    if lines:
        return "\n".join(lines)
    return f"- {placeholder}"


def _friendly_fact_type(ft: str) -> str:
    mapping = {
        "ROUND_SWING": "关键回合/势头反转",
        "ECONOMIC_PATTERN": "经济节奏与强起",
        "FORCE_BUY_ROUND": "强起决策",
        "ECO_COLLAPSE_SEQUENCE": "经济崩溃",
        "HIGH_RISK_SEQUENCE": "高风险推进",
        "MID_ROUND_TIMING_PATTERN": "中期节奏",
        "OBJECTIVE_LOSS_CHAIN": "目标控制缺失",
        "MAP_WEAK_POINT": "地图薄弱点",
        "PLAYER_IMPACT_STAT": "选手关键行为",
    }
    return mapping.get(ft, ft or "关键观察")


def _impact_suggestion(ft: str) -> Tuple[str, str]:
    if ft in {"ECONOMIC_PATTERN", "FORCE_BUY_ROUND", "ECO_COLLAPSE_SEQUENCE"}:
        return (
            "【影响】经济节奏被打断/强起失败加剧逆风。",
            "【建议】明确强起条件，保留关键道具，必要时选择 save 稳经济。",
        )
    if ft in {"ROUND_SWING", "HIGH_RISK_SEQUENCE"}:
        return (
            "【影响】关键回合失利拉低整场胜率。",
            "【建议】复盘当回合的交换路径与信息量，设定硬条件再执行。",
        )
    if ft in {"MAP_WEAK_POINT", "OBJECTIVE_LOSS_CHAIN"}:
        return (
            "【影响】重点区域失控，导致连环失分。",
            "【建议】加强该区域前置信息和支援链路，必要时调整首发配置。",
        )
    return (
        "【影响】可能放大对局波动，降低稳定性。",
        "【建议】补充样本并针对性演练，确保可交易与信息闭环。",
    )


def _group_and_limit(facts: List[Dict[str, Any]], max_items: int = SECTION_FACT_TOP_K) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"items": [], "extra": 0})
    for f in facts:
        ft = f.get("fact_type") or "UNKNOWN"
        scope = f.get("scope") or {}
        key = (
            ft,
            scope.get("round") or scope.get("round_range") or f.get("round") or f.get("round_range"),
            scope.get("team_id") or f.get("team_id"),
            f.get("pattern_type") or f.get("pattern") or f.get("note"),
        )
        bucket = grouped[ft]
        if any(
            (existing.get("_dedup_key") == key)
            for existing in bucket["items"]
        ):
            continue
        f = dict(f)
        f["_dedup_key"] = key
        if len(bucket["items"]) < max_items:
            bucket["items"].append(f)
        else:
            bucket["extra"] += 1
    return grouped


def _render_section(ft: str, grouped: Dict[str, Any]) -> str:
    friendly = _friendly_fact_type(ft)
    items = grouped.get("items") or []
    extra = grouped.get("extra") or 0
    lines: List[str] = []

    # 结论句
    if items or extra:
        lines.append(f"{friendly}：出现反复问题，需要优先复盘。")
    else:
        lines.append(f"{friendly}：当前证据不足，仅提供占位结论。")

    # 示例
    for f in items:
        note = f.get("note") or friendly
        metrics = f.get("metrics") or {}
        sample = metrics.get("sample_size") or f.get("evidence", {}).get("sample_size")
        detail = []
        for k, v in metrics.items():
            if k == "sample_size":
                continue
            if isinstance(v, float):
                detail.append(f"{k}={v:.2f}")
            elif isinstance(v, (int, str)):
                detail.append(f"{k}={v}")
        suffix = f" (n={sample})" if sample else ""
        metric_part = f" | {'; '.join(detail)}" if detail else ""
        lines.append(f"- {note}{metric_part}{suffix}")

    if extra > 0:
        lines.append(f"此外观察到 {extra} 次类似情况，建议在会议中集中复盘。")

    impact, suggestion = _impact_suggestion(ft)
    lines.append(impact)
    lines.append(suggestion)
    return "\n".join(lines)


def _synthesize_player_insight(facts: List[Dict[str, Any]], scope: Dict[str, Any]) -> NarrativeResult:
    norm_facts = [_normalize_fact(f) for f in facts if f.get("fact_type") and f.get("fact_type") != "CONTEXT_ONLY"]
    player_name = scope.get("player_name") or scope.get("player") or "该选手"
    data_points: List[str] = []
    impacts: List[str] = []
    actions: List[str] = []

    for nf in norm_facts:
        dp = _format_datapoint(nf)
        data_points.append(dp)
        metrics = nf.get("metrics") or {}
        impact_note = nf.get("note") or "与团队结果存在关联"
        if "loss_rate" in metrics:
            impact_note = f"回合失败率 {metrics['loss_rate']:.2f}，对局结果受影响明显"
        elif metrics.get("rounds_lost_after"):
            impact_note = f"相关情形后输掉 {metrics['rounds_lost_after']} 回合，需关注可交易性"
        impacts.append(f"- {impact_note}")

        if nf.get("fact_type") in {"PLAYER_IMPACT_STAT", "ROUND_SWING"}:
            actions.append("- 优化首轮交火与支援时机，确保可交易，避免无支援首死")
        elif nf.get("fact_type") in {"HIGH_RISK_SEQUENCE"}:
            actions.append("- 复盘高风险推进的站位与时间点，明确提前信息与道具支持")

    template = _load_template("player_insight.md")
    content = template.format(
        data_points=_ensure_non_empty_block(data_points, "- 基于当前可用数据的初步复盘（低置信度）"),
        interpretations=_ensure_non_empty_block(impacts, "- 证据不足，影响关系待补充"),
        actions=_ensure_non_empty_block(actions, "- 提示：确保关键回合的可交易与交火条件"),
    )
    content = refine_narrative(content, NarrativeType.PLAYER_INSIGHT_REPORT.value)
    used = len(norm_facts)
    confidence = min(0.9, 0.5 + min(used / 8.0, 0.3)) if used else 0.35
    return NarrativeResult(
        narrative_type=NarrativeType.PLAYER_INSIGHT_REPORT,
        content=content,
        confidence=confidence,
        used_facts=used,
    )


def _synthesize_match_review(facts: List[Dict[str, Any]], scope: Dict[str, Any]) -> NarrativeResult:
    norm_facts = [_normalize_fact(f) for f in facts if f.get("fact_type") and f.get("fact_type") != "CONTEXT_ONLY"]
    grouped = _group_and_limit(norm_facts, max_items=SECTION_FACT_TOP_K)

    ordered_types = [
        "ECONOMIC_PATTERN",
        "FORCE_BUY_ROUND",
        "ECO_COLLAPSE_SEQUENCE",
        "ROUND_SWING",
        "HIGH_RISK_SEQUENCE",
        "MID_ROUND_TIMING_PATTERN",
        "OBJECTIVE_LOSS_CHAIN",
        "MAP_WEAK_POINT",
    ]

    sections: List[str] = []
    for ft in ordered_types:
        sections.append(_render_section(ft, grouped.get(ft, {})))

    content_lines: List[str] = []
    overview = f"赛制：{scope.get('match_format') or '未知'}；对手：{scope.get('opponent') or '未知'}；地图：{scope.get('map') or scope.get('map_name') or '未知'}"
    content_lines.append(f"复盘要点：本场主要问题集中在经济节奏与关键回合执行（若证据不足则视为低置信度）。")
    content_lines.append(f"【概览】{overview}")
    content_lines.extend(sections)
    content = "\n\n".join(content_lines)
    content = refine_narrative(content, NarrativeType.MATCH_REVIEW_AGENDA.value)
    used = len(norm_facts)
    confidence = min(0.85, 0.55 + min(used / 10.0, 0.25)) if used else 0.3
    return NarrativeResult(
        narrative_type=NarrativeType.MATCH_REVIEW_AGENDA,
        content=content,
        confidence=confidence,
        used_facts=used,
    )


def _synthesize_match_summary(facts: List[Dict[str, Any]], scope: Dict[str, Any]) -> NarrativeResult:
    norm_facts = [_normalize_fact(f) for f in facts if f.get("fact_type") and f.get("fact_type") != "CONTEXT_ONLY"]
    grouped = _group_and_limit(norm_facts, max_items=SECTION_FACT_TOP_K)

    ordered_types = [
        "ROUND_SWING",
        "ECONOMIC_PATTERN",
        "OBJECTIVE_LOSS_CHAIN",
        "MAP_WEAK_POINT",
    ]

    sections: List[str] = []
    for ft in ordered_types:
        bucket = grouped.get(ft, {})
        if bucket.get("items") or bucket.get("extra"):
            sections.append(_render_section(ft, bucket))

    if not sections:
        sections.append(
            "当前比赛在该维度上的直接证据有限。\n"
            "基于已有的回合级与聚合数据，可以初步观察到以下趋势：\n"
            "- 样本不足，需结合录像与战术复盘补充。\n"
            "建议在赛后会议中，结合录像与战术复盘进一步验证。"
        )

    overview = f"赛制：{scope.get('match_format') or '未知'}；地图：{scope.get('map') or scope.get('map_name') or '未知'}；对手：{scope.get('opponent') or '未知'}"
    content_lines = ["关键教训摘要（低置信占位）：", overview]
    content_lines.extend(sections)
    content = "\n\n".join(content_lines)
    content = refine_narrative(content, NarrativeType.SUMMARY_REPORT.value)
    used = len(norm_facts)
    confidence = 0.35 if not used else min(0.8, 0.5 + min(used / 12.0, 0.25))
    return NarrativeResult(
        narrative_type=NarrativeType.SUMMARY_REPORT,
        content=content,
        confidence=confidence,
        used_facts=used,
    )


def synthesize_narrative(narrative_type: NarrativeType, facts: List[Dict[str, Any]], scope: Dict[str, Any]) -> NarrativeResult:
    if narrative_type == NarrativeType.PLAYER_INSIGHT_REPORT:
        return _synthesize_player_insight(facts, scope)
    if narrative_type == NarrativeType.MATCH_REVIEW_AGENDA:
        return _synthesize_match_review(facts, scope)
    if narrative_type == NarrativeType.SUMMARY_REPORT:
        return _synthesize_match_summary(facts, scope)
    raise ValueError(f"Unsupported narrative type: {narrative_type}")
