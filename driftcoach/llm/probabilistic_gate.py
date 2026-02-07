"""
Probabilistic Evidence Gate
Transform binary decisions into calibrated confidence scores.

Goal: Replace hardcoded thresholds with probabilistic functions that:
1. Return continuous confidence scores (0-1)
2. Classify into 3 states: ACCEPT / LOW_CONFIDENCE / REJECT
3. Consider sample size, variance, and historical performance
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math


class GateDecision(Enum):
    """Three-way decision (not binary)"""
    ACCEPT = "accept"           # Sufficient evidence, high confidence
    LOW_CONFIDENCE = "low_confidence"  # Borderline, can proceed with caveats
    REJECT = "reject"           # Insufficient evidence, should not proceed


@dataclass
class GateMetrics:
    """Input metrics for gate decision"""
    # Sample size metrics
    states_count: int = 0           # Number of game states
    series_pool: int = 0            # Number of series/matches
    agg_performance: int = 0        # Aggregated performance data points

    # Data quality metrics
    outcome_field_available: bool = False  # Whether outcome field exists
    aggregation_available: bool = False     # Whether aggregation succeeded
    has_event_data: bool = False            # Whether event-level data exists

    # Variance metrics (optional, requires computation)
    outcome_variance: Optional[float] = None      # Variance in outcomes
    performance_variance: Optional[float] = None  # Variance in performance

    # Historical metrics (requires memory layer - placeholder)
    historical_hit_rate: float = 0.5      # Historical acceptance rate
    recent_failure_rate: float = 0.0      # Recent rejection rate


@dataclass
class GateResult:
    """Output of probabilistic gate"""
    decision: GateDecision
    confidence: float              # 0-1 overall confidence
    score_breakdown: Dict[str, float]  # Individual component scores
    rationale: List[str]            # Human-readable reasons
    suggested_action: Optional[str] = None  # What to do next


def sigmoid(x: float, center: float = 0.5, steepness: float = 10) -> float:
    """
    Sigmoid function for smooth transitions.
    Maps x in [0, 1] to output in [0, 1] with adjustable center and steepness.
    """
    # Shift x so center becomes 0
    shifted = (x - center) * steepness
    # Standard sigmoid: 1 / (1 + e^-x)
    return 1.0 / (1.0 + math.exp(-shifted))


def compute_sample_size_score(metrics: GateMetrics) -> float:
    """
    Sample size sufficiency: 0-1 score based on states_count and series_pool.

    Uses logarithmic scaling: diminishing returns after certain thresholds.
    """
    # Minimum viable samples: 10 states, 1 series
    min_states = 10
    min_series = 1

    # Ideal targets: 50 states, 5 series (not hard limits, but saturation points)
    target_states = 50
    target_series = 5

    # States score: log-scale
    if metrics.states_count < min_states:
        states_score = 0.0
    else:
        # Log from min to target, capped at 1.0
        normalized = (metrics.states_count - min_states) / (target_states - min_states)
        states_score = min(1.0, normalized)

    # Series score: also log-scale but with higher weight
    if metrics.series_pool < min_series:
        series_score = 0.0
    else:
        normalized = (metrics.series_pool - min_series) / (target_series - min_series)
        series_score = min(1.0, normalized)

    # Weighted combination (series matter more than individual states)
    return 0.4 * states_score + 0.6 * series_score


def compute_data_quality_score(metrics: GateMetrics) -> float:
    """
    Data quality: 0-1 score based on field availability and aggregation success.

    Penalizes missing outcome fields, rewards aggregation availability.
    """
    score = 0.0

    # Outcome field is critical
    if metrics.outcome_field_available:
        score += 0.4

    # Aggregation is very useful
    if metrics.aggregation_available:
        score += 0.3

    # Event data is required for certain intents
    if metrics.has_event_data:
        score += 0.2

    # Aggregated performance data adds confidence
    if metrics.agg_performance > 0:
        # Scale by amount of data (diminishing returns)
        agg_score = min(1.0, metrics.agg_performance / 10.0)  # 10+ data points = full score
        score += 0.1 * agg_score

    return min(1.0, score)


def compute_variance_penalty(metrics: GateMetrics) -> float:
    """
    Variance penalty: 0-1 score where high variance = low score.

    High variance in outcomes suggests noisy data.
    Requires variance metrics (optional, returns neutral if missing).
    """
    if metrics.outcome_variance is None and metrics.performance_variance is None:
        # No variance data → neutral penalty (neither help nor hurt)
        return 0.5

    penalties = []

    # Outcome variance: lower is better
    if metrics.outcome_variance is not None:
        # Variance > 1.0 is high (binary outcomes would have variance ~0.25)
        outcome_penalty = 1.0 / (1.0 + metrics.outcome_variance)
        penalties.append(outcome_penalty)

    # Performance variance: depends on metric, but generally lower is more consistent
    if metrics.performance_variance is not None:
        perf_penalty = 1.0 / (1.0 + metrics.performance_variance)
        penalties.append(perf_penalty)

    if not penalties:
        return 0.5

    # Average of available penalties
    return sum(penalties) / len(penalties)


def compute_historical_adjustment(metrics: GateMetrics) -> float:
    """
    Historical adjustment: 0-1 score based on past gate performance.

    If historical hit rate is low, reduce confidence.
    If recent failure rate is high, reduce confidence more aggressively.

    Requires memory layer (currently returns neutral).
    """
    # Base adjustment from historical hit rate
    hit_rate_adjustment = metrics.historical_hit_rate  # 0.5 = neutral

    # Penalty for recent failures
    recent_failure_penalty = 1.0 - (metrics.recent_failure_rate * 0.5)

    # Combined adjustment
    return hit_rate_adjustment * recent_failure_penalty


def probabilistic_evidence_gate(
    metrics: GateMetrics,
    intent: Optional[str] = None,
    strictness: float = 0.5,
) -> GateResult:
    """
    Probabilistic evidence gate.

    Args:
        metrics: Input metrics (sample size, quality, variance, history)
        intent: Optional intent type (for future intent-specific tuning)
        strictness: Gate strictness (0=permissive, 0.5=balanced, 1=strict)

    Returns:
        GateResult with decision, confidence, breakdown, and rationale
    """
    # Compute individual scores
    sample_score = compute_sample_size_score(metrics)
    quality_score = compute_data_quality_score(metrics)
    variance_penalty = compute_variance_penalty(metrics)
    historical_adjustment = compute_historical_adjustment(metrics)

    # Component weights (can be tuned per-intent in future)
    weights = {
        "sample": 0.35,
        "quality": 0.35,
        "variance": 0.15,
        "historical": 0.15,
    }

    # Weighted combination
    base_confidence = (
        weights["sample"] * sample_score +
        weights["quality"] * quality_score +
        weights["variance"] * variance_penalty +
        weights["historical"] * historical_adjustment
    )

    # Apply strictness bias (strict=shift threshold left, permissive=shift right)
    # strictness=0.5 is neutral, <0.5 is permissive, >0.5 is strict
    biased_confidence = sigmoid(base_confidence, center=1.0-strictness, steepness=6)

    # Clamp to valid range
    final_confidence = max(0.0, min(1.0, biased_confidence))

    # Score breakdown for transparency
    score_breakdown = {
        "sample_size": sample_score,
        "data_quality": quality_score,
        "variance_penalty": variance_penalty,
        "historical_adjustment": historical_adjustment,
        "base_confidence": base_confidence,
        "final_confidence": final_confidence,
    }

    # Decision thresholds (can be adjusted based on strictness)
    # ACCEPT: confidence >= 0.7
    # LOW_CONFIDENCE: 0.4 <= confidence < 0.7
    # REJECT: confidence < 0.4
    if final_confidence >= 0.7:
        decision = GateDecision.ACCEPT
        rationale = [
            f"Sample size adequate (score={sample_score:.2f})",
            f"Data quality acceptable (score={quality_score:.2f})",
            f"Overall confidence {final_confidence:.2f}",
        ]
        suggested_action = "proceed_with_analysis"

    elif final_confidence >= 0.4:
        decision = GateDecision.LOW_CONFIDENCE
        rationale = [
            f"Sample size borderline (score={sample_score:.2f})",
            f"Data quality limited (score={quality_score:.2f})",
            f"Overall confidence {final_confidence:.2f} - proceed with caveats",
        ]
        suggested_action = "proceed_with_degraded_analysis"

    else:
        decision = GateDecision.REJECT
        rationale = [
            f"Insufficient sample size (score={sample_score:.2f})",
            f"Data quality inadequate (score={quality_score:.2f})",
            f"Overall confidence {final_confidence:.2f} - insufficient evidence",
        ]
        suggested_action = "request_more_data_or_decline"

    return GateResult(
        decision=decision,
        confidence=final_confidence,
        score_breakdown=score_breakdown,
        rationale=rationale,
        suggested_action=suggested_action,
    )


def legacy_gate_wrapper(
    context: Dict[str, Any],
    recent_evidence: List[Any],
    intent: Optional[str] = None,
    required_facts: Optional[List[str]] = None,
) -> Tuple[str, List[str]]:
    """
    Wrapper to maintain backward compatibility with old evidence_gate interface.

    Maps old {INSUFFICIENT, SUFFICIENT} to new {REJECT, ACCEPT, LOW_CONFIDENCE}.
    """
    # Extract metrics from old context format
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

    # Build metrics
    metrics = GateMetrics(
        states_count=states_count,
        series_pool=series_pool,
        agg_performance=agg_perf,
        outcome_field_available=(outcome_field != "NOT_FOUND"),
        aggregation_available=aggregation_available,
        has_event_data=is_event_intent,
        # Variance and historical metrics not available in old format
        outcome_variance=None,
        performance_variance=None,
        historical_hit_rate=0.5,  # Neutral prior
        recent_failure_rate=0.0,
    )

    # Call new probabilistic gate
    result = probabilistic_evidence_gate(metrics, intent=intent)

    # Map new decision to old format
    decision_map = {
        GateDecision.ACCEPT: "SUFFICIENT",
        GateDecision.LOW_CONFIDENCE: "SUFFICIENT",  # Treat low-confidence as sufficient (with warnings)
        GateDecision.REJECT: "INSUFFICIENT",
    }

    old_decision = decision_map[result.decision]
    old_reasons = result.rationale

    return old_decision, old_reasons
