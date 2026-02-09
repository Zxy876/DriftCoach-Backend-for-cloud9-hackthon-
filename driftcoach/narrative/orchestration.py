from __future__ import annotations

from typing import Dict, List, Any, Optional, Tuple

from driftcoach.hackathon.series_pipeline import hackathon_mine_and_analyze
from driftcoach.config.bounds import (
    SystemBounds,
    DEFAULT_BOUNDS,
    enforce_bounds_on_intents,
    BoundEnforcer,
)

MATCH_REVIEW_ORCHESTRATION: Dict[str, Any] = {
    "required_intents": [
        "ECONOMIC_COUNTERFACTUAL",
        "MOMENTUM_ANALYSIS",
        "MAP_WEAK_POINT",
    ],
    "force_file_download": True,
    "min_facts_threshold": {
        "ROUND_SWING": 1,
        "ECO_COLLAPSE_SEQUENCE": 1,
    },
}

PLAYER_REVIEW_ORCHESTRATION: Dict[str, Any] = {
    "required_intents": [
        "PLAYER_REVIEW",
        "MOMENTUM_ANALYSIS",
        "STABILITY_ANALYSIS",
    ],
    "force_file_download": True,
    "min_facts_threshold": {
        "PLAYER_IMPACT_STAT": 1,
        "ROUND_SWING": 1,
    },
}

ORCHESTRATION_MAP = {
    "MATCH_REVIEW": MATCH_REVIEW_ORCHESTRATION,
    "PLAYER_REVIEW": PLAYER_REVIEW_ORCHESTRATION,
}

INTENT_FACT_MAP: Dict[str, List[str]] = {
    "RISK_ASSESSMENT": ["HIGH_RISK_SEQUENCE", "ROUND_SWING"],
    "ECONOMIC_COUNTERFACTUAL": ["FORCE_BUY_ROUND", "ECO_COLLAPSE_SEQUENCE", "ECONOMIC_PATTERN"],
    "MOMENTUM_ANALYSIS": ["ROUND_SWING"],
    "STABILITY_ANALYSIS": ["ROUND_SWING", "HIGH_RISK_SEQUENCE"],
    "EXECUTION_VS_STRATEGY": ["OBJECTIVE_LOSS_CHAIN", "ROUND_SWING"],
    "MAP_WEAK_POINT": ["OBJECTIVE_LOSS_CHAIN", "HIGH_RISK_SEQUENCE"],
    "PLAYER_REVIEW": ["PLAYER_IMPACT_STAT", "ROUND_SWING"],
    "COUNTERFACTUAL_PLAYER_IMPACT": ["CONTEXT_ONLY"],
    "MATCH_SUMMARY": ["CONTEXT_ONLY"],
}


def _build_mining_plan(intent: str, series_id: str, player_id: Optional[str], player_name: Optional[str]) -> Dict[str, Any]:
    return {
        "intent": intent,
        "question_type": "SUMMARY",
        "required_facts": INTENT_FACT_MAP.get(intent, []),
        "scope": {
            "series_id": series_id,
            "player": {"id": player_id, "name": player_name} if (player_id or player_name) else None,
        },
        "temporal_focus": {
            "granularity": "round",
            "range": "entire_series",
        },
        "constraints": {
            "min_samples": 1,
            "confidence_threshold": 0.3,
        },
    }


def run_narrative_orchestration(
    intent: str,
    api_key: str,
    series_id: str,
    base_query: str,
    player_id: Optional[str] = None,
    player_name: Optional[str] = None,
    bounds: SystemBounds = DEFAULT_BOUNDS,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    plan_cfg = ORCHESTRATION_MAP.get(intent)
    if not plan_cfg:
        return [], []

    aggregated_evidence: List[Dict[str, Any]] = []
    aggregated_nodes: List[Dict[str, Any]] = []

    # Enforce max_sub_intents bound
    required_intents = plan_cfg.get("required_intents") or []
    bounded_intents = enforce_bounds_on_intents(required_intents, bounds=bounds)

    # Use bound enforcer to track compliance
    with BoundEnforcer(bounds=bounds) as enforcer:
        enforcer.check_sub_intent_count(len(bounded_intents))

        for sub_intent in bounded_intents:
            mining_plan = _build_mining_plan(sub_intent, series_id, player_id, player_name)
            sub_query = f"[auto-narrative:{intent}->{sub_intent}] {base_query}"
            plan, evidence, nodes, resolution = hackathon_mine_and_analyze(
                api_key,
                series_id,
                sub_query,
                player_focus=player_id,
                player_name=player_name,
                mining_plan=mining_plan,
                should_force_fd=True,
            )
            aggregated_evidence.extend(evidence or [])
            aggregated_nodes.extend(nodes or [])

    return aggregated_evidence, aggregated_nodes
