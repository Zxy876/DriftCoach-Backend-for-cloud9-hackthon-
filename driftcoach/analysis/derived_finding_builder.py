from __future__ import annotations

from typing import Dict, List, Tuple

from driftcoach.question_state import DerivedFinding, FactRef, QuestionState


FACT_TYPE_TO_FINDING = {
    "ECONOMIC_PATTERN": "ECON_PROBLEM",
    "FORCE_BUY_ROUND": "ECON_PROBLEM",
    "ECO_COLLAPSE_SEQUENCE": "ECON_PROBLEM",
    "ECONOMY_COLLAPSE": "ECON_PROBLEM",
    "MAP_WEAK_POINT": "MAP_WEAKNESS",
    "OBJECTIVE_LOSS_CHAIN": "MAP_WEAKNESS",
    "SITE_LOSS_CHAIN": "MAP_WEAKNESS",
    "ROUND_SWING": "MOMENTUM_SHIFT",
    "TURNING_POINT": "MOMENTUM_SHIFT",
    "MOMENTUM_SHIFT": "MOMENTUM_SHIFT",
    "PLAYER_IMPACT_STAT": "PLAYER_RISK",
    "HIGH_RISK_SEQUENCE": "PLAYER_RISK",
}


def _confidence_from_fact_refs(facts: List[FactRef]) -> float:
    if not facts:
        return 0.35
    return min(0.9, sum(f.confidence for f in facts) / len(facts))


def _finding_scope(intent: str) -> str:
    if intent == "SUMMARY":
        return "SUMMARY"
    if intent == "MATCH_REVIEW":
        return "MAP"
    if intent == "PLAYER_REVIEW":
        return "PLAYER"
    if intent == "ECONOMIC_ISSUE":
        return "ECON"
    return "UNKNOWN"


def build_findings_from_facts(question_state: QuestionState, facts: List[Dict]) -> List[DerivedFinding]:
    findings: List[DerivedFinding] = []
    for f in facts:
        fact_type = f.get("fact_type") or f.get("type") or "UNKNOWN"
        finding_type = FACT_TYPE_TO_FINDING.get(fact_type)
        if not finding_type:
            continue
        fact_ref = FactRef.from_fact(f, default_type=fact_type)
        summary = f.get("note") or f.get("description") or fact_type
        finding_id = f.get("derived_id") or f"df-{fact_ref.id}"
        finding = DerivedFinding(
            id=finding_id,
            type=finding_type,
            scope=question_state.scope,
            summary=summary,
            supporting_facts=[fact_ref],
            confidence=fact_ref.confidence,
        )
        findings.append(finding)
    return findings


def reuse_findings_from_pool(question_state: QuestionState, pool: List[DerivedFinding], threshold: float = 0.45) -> List[DerivedFinding]:
    return [f for f in pool if f.confidence >= threshold]


def evaluate_question(findings: List[DerivedFinding]) -> Tuple[str, float]:
    if not findings:
        return "INSUFFICIENT", 0.2
    conf = min(0.9, sum(f.confidence for f in findings) / len(findings))
    if conf >= 0.65:
        return "ANSWERED", conf
    return "WEAK", conf
