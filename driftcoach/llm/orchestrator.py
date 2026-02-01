"""
Deterministic AI Inference Orchestrator with evidence gate.
Goal: when key facts are missing, force EVIDENCE_INSUFFICIENT and emit 1-2 patches.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

MAX_RATIONALE_CHARS = 600


def _clip(text: str, limit: int = MAX_RATIONALE_CHARS) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def evidence_gate(
    context: Dict[str, Any],
    recent_evidence: List[Any],
    intent: Optional[str] = None,
    required_facts: Optional[List[str]] = None,
) -> Tuple[str, List[str]]:
    """Returns (decision, reasons). decision in {INSUFFICIENT, SUFFICIENT}."""
    reasons: List[str] = []
    schema = context.get("schema", {}) or {}
    ev = context.get("evidence", {}) or {}
    req_facts = required_facts or []
    is_event_intent = any(str(fact).endswith("_ROUND") or str(fact).endswith("_SEQUENCE") for fact in req_facts)

    outcome_field = schema.get("outcome_field") or schema.get("outcomeField") or "UNKNOWN"
    aggregation_available = bool(ev.get("aggregation_available"))
    states_count = int(ev.get("states_count", 0) or 0)
    series_pool = int(ev.get("seriesPool", ev.get("series_pool", 0) or 0))
    by_type = ev.get("by_type", {}) or {}
    agg_perf = int(by_type.get("AGGREGATED_PERFORMANCE", 0) or 0)

    # Hard insufficient conditions
    if outcome_field == "NOT_FOUND" and not aggregation_available:
        reasons.append("outcome_field_not_found_and_no_aggregation")
    if states_count < 20:
        reasons.append("states_lt_20")
    if series_pool == 0 and not is_event_intent:
        reasons.append("series_pool_zero")
    if agg_perf == 0:
        reasons.append("agg_performance_zero")

    if reasons:
        return "INSUFFICIENT", reasons

    # SUFFICIENT only if all of these hold
    if states_count >= 20 and (outcome_field != "NOT_FOUND" or agg_perf >= 2) and series_pool > 0:
        return "SUFFICIENT", ["states_ge_20", "aggregation_present", "series_pool_gt_0"]

    return "INSUFFICIENT", ["fallback_insufficient"]


def _default_patches(anchor_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Patch 1: enumerate series ±180d, limit 200
    patches: List[Dict[str, Any]] = [
        {
            "patch_type": "ENUMERATE_SERIES",
            "target_entity": "series",
            "params": {
                "window": {"gte": "-180d", "lte": "+180d"},
                "limit": 200,
            },
            "expected_evidence_type": "CONTEXT_ONLY",
        }
    ]

    # Patch 2: aggregate team statistics (best-effort)
    team_ids = anchor_context.get("team_ids") or []
    team_id = team_ids[0] if team_ids else anchor_context.get("team_id", "unknown")
    patches.append(
        {
            "patch_type": "AGGREGATE_TEAM_STATISTICS",
            "target_entity": "team",
            "params": {
                "team_id": team_id,
                "series_ids": [],  # executor may fill from enumerate results later
            },
            "expected_evidence_type": "AGGREGATED_PERFORMANCE",
        }
    )

    return patches


def generate_inference_plan(inference_input: Dict[str, Any]) -> Dict[str, Any]:
    ctx = inference_input.get("context", {})
    intent = inference_input.get("intent")

    if intent in {"COUNTERFACTUAL_PLAYER_IMPACT", "MATCH_SUMMARY"}:
        return {
            "intent": intent,
            "judgment": "EVIDENCE_SUFFICIENT",
            "rationale": "intent-bypass",
            "missing_evidence": [],
            "proposed_patches": [],
            "confidence_note": "intent-bypass",
        }
    gate_decision, reasons = evidence_gate(
        ctx,
        inference_input.get("recent_evidence", []),
        intent=intent,
        required_facts=inference_input.get("required_facts"),
    )

    if gate_decision == "INSUFFICIENT":
        rationale = _clip("; ".join(reasons))
        return {
            "intent": intent,
            "judgment": "EVIDENCE_INSUFFICIENT",
            "rationale": rationale,
            "missing_evidence": [],
            "proposed_patches": _default_patches(inference_input.get("context", {})),
            "confidence_note": "gate-insufficient",
        }

    # SUFFICIENT (deterministic)
    rationale = _clip("; ".join(reasons) or "evidence meets gate thresholds")
    return {
        "intent": intent,
        "judgment": "EVIDENCE_SUFFICIENT",
        "rationale": rationale,
        "missing_evidence": [],
        "proposed_patches": [],
        "confidence_note": "gate-sufficient",
    }
