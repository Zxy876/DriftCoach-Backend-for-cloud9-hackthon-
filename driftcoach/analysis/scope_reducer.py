from __future__ import annotations

from typing import Dict, List, Tuple

from driftcoach.question_state import DerivedFinding, QuestionState


ECON_FACT_TYPES = {
    "ECONOMIC_PATTERN",
    "FORCE_BUY_ROUND",
    "ECO_COLLAPSE_SEQUENCE",
    "ECONOMY_COLLAPSE",
}

MAP_FACT_TYPES = {
    "MAP_WEAK_POINT",
    "OBJECTIVE_LOSS_CHAIN",
    "SITE_LOSS_CHAIN",
}

MOMENTUM_FACT_TYPES = {
    "ROUND_SWING",
    "TURNING_POINT",
    "MOMENTUM_SHIFT",
}

PLAYER_FACT_TYPES = {
    "PLAYER_IMPACT_STAT",
    "HIGH_RISK_SEQUENCE",
}


def _allowed_finding_types(scope: str, intent: str) -> List[str]:
    if intent == "MATCH_REVIEW":
        return ["ECON_PROBLEM", "MAP_WEAKNESS", "MOMENTUM_SHIFT", "PLAYER_RISK"]
    if intent == "SUMMARY":
        return ["ECON_PROBLEM", "MAP_WEAKNESS", "MOMENTUM_SHIFT", "PLAYER_RISK"]
    if scope == "ECON":
        return ["ECON_PROBLEM"]
    if scope == "MAP":
        return ["MAP_WEAKNESS"]
    if scope == "PLAYER":
        return ["PLAYER_RISK"]
    return ["ECON_PROBLEM", "MAP_WEAKNESS", "MOMENTUM_SHIFT", "PLAYER_RISK"]


def _filter_facts_by_scope(scope: str, facts: List[Dict]) -> List[Dict]:
    if scope == "ECON":
        return [f for f in facts if (f.get("fact_type") or f.get("type")) in ECON_FACT_TYPES]
    if scope == "MAP":
        return [f for f in facts if (f.get("fact_type") or f.get("type")) in MAP_FACT_TYPES]
    if scope == "PLAYER":
        return [f for f in facts if (f.get("fact_type") or f.get("type")) in PLAYER_FACT_TYPES]
    return list(facts)


def reduce_scope(question_state: QuestionState, session_state: "SessionQAState") -> Tuple[List[Dict], List[DerivedFinding]]:
    """Limit usable facts/findings according to intent-scope mapping."""

    filtered_facts = _filter_facts_by_scope(question_state.scope, question_state.available_facts)

    allowed_types = set(_allowed_finding_types(question_state.scope, question_state.intent))
    filtered_findings = [f for f in session_state.findings_pool if f.type in allowed_types]

    return filtered_facts, filtered_findings
