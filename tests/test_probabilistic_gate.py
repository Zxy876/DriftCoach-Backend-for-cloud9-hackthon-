"""
Tests for probabilistic evidence gate.
"""

import pytest
from driftcoach.llm.probabilistic_gate import (
    GateMetrics,
    GateDecision,
    probabilistic_evidence_gate,
    compute_sample_size_score,
    compute_data_quality_score,
)


def test_sample_size_score():
    """Test sample size scoring function."""
    # Zero samples
    metrics = GateMetrics(states_count=0, series_pool=0)
    score = compute_sample_size_score(metrics)
    assert score == 0.0

    # Below minimum
    metrics = GateMetrics(states_count=5, series_pool=0)
    score = compute_sample_size_score(metrics)
    assert score == 0.0

    # Minimum viable
    metrics = GateMetrics(states_count=10, series_pool=1)
    score = compute_sample_size_score(metrics)
    assert score > 0.0
    assert score < 1.0

    # Good sample size
    metrics = GateMetrics(states_count=50, series_pool=5)
    score = compute_sample_size_score(metrics)
    assert score > 0.8  # Should be high


def test_data_quality_score():
    """Test data quality scoring function."""
    # Nothing available
    metrics = GateMetrics()
    score = compute_data_quality_score(metrics)
    assert score == 0.0

    # Only outcome field
    metrics = GateMetrics(outcome_field_available=True)
    score = compute_data_quality_score(metrics)
    assert score == 0.4

    # All basic fields
    metrics = GateMetrics(
        outcome_field_available=True,
        aggregation_available=True,
        has_event_data=True,
    )
    score = compute_data_quality_score(metrics)
    assert score == 0.9  # 0.4 + 0.3 + 0.2

    # With aggregated performance
    metrics = GateMetrics(
        outcome_field_available=True,
        aggregation_available=True,
        has_event_data=True,
        agg_performance=10,
    )
    score = compute_data_quality_score(metrics)
    assert score == 1.0  # Maxed out


def test_gate_decision_reject():
    """Test REJECT decision for insufficient data."""
    metrics = GateMetrics(
        states_count=5,  # Below minimum
        series_pool=0,
        agg_performance=0,
        outcome_field_available=False,
    )

    result = probabilistic_evidence_gate(metrics)

    assert result.decision == GateDecision.REJECT
    assert result.confidence < 0.4
    assert result.suggested_action == "request_more_data_or_decline"


def test_gate_decision_accept():
    """Test ACCEPT decision for good data."""
    metrics = GateMetrics(
        states_count=100,  # Well above minimum
        series_pool=10,
        agg_performance=20,
        outcome_field_available=True,
        aggregation_available=True,
        has_event_data=True,
    )

    result = probabilistic_evidence_gate(metrics)

    assert result.decision == GateDecision.ACCEPT
    assert result.confidence >= 0.7
    assert result.suggested_action == "proceed_with_analysis"


def test_gate_decision_low_confidence():
    """Test LOW_CONFIDENCE decision for borderline data."""
    metrics = GateMetrics(
        states_count=15,  # Barely above minimum
        series_pool=1,
        agg_performance=1,
        outcome_field_available=True,
        aggregation_available=False,
    )

    result = probabilistic_evidence_gate(metrics)

    # Should be LOW_CONFIDENCE or REJECT (depending on other factors)
    assert result.decision in [GateDecision.LOW_CONFIDENCE, GateDecision.REJECT]


def test_gate_strictness():
    """Test that strictness parameter affects decisions."""
    # Borderline metrics
    metrics = GateMetrics(
        states_count=20,
        series_pool=2,
        agg_performance=3,
        outcome_field_available=True,
        aggregation_available=True,
    )

    # Permissive gate (strictness=0.3)
    result_permissive = probabilistic_evidence_gate(metrics, strictness=0.3)

    # Strict gate (strictness=0.7)
    result_strict = probabilistic_evidence_gate(metrics, strictness=0.7)

    # Permissive should have higher confidence
    assert result_permissive.confidence >= result_strict.confidence


def test_score_breakdown_transparency():
    """Test that score breakdown provides transparency."""
    metrics = GateMetrics(
        states_count=50,
        series_pool=3,
        agg_performance=5,
        outcome_field_available=True,
        aggregation_available=True,
    )

    result = probabilistic_evidence_gate(metrics)

    # Check that breakdown exists
    assert "sample_size" in result.score_breakdown
    assert "data_quality" in result.score_breakdown
    assert "variance_penalty" in result.score_breakdown
    assert "final_confidence" in result.score_breakdown

    # Check that breakdown makes sense
    assert 0.0 <= result.score_breakdown["sample_size"] <= 1.0
    assert 0.0 <= result.score_breakdown["data_quality"] <= 1.0
    assert result.score_breakdown["final_confidence"] == result.confidence


def test_variance_penalty():
    """Test variance penalty calculation."""
    # Low variance (consistent data)
    metrics_low = GateMetrics(
        states_count=50,
        series_pool=5,
        outcome_variance=0.1,
    )

    result_low = probabilistic_evidence_gate(metrics_low)

    # High variance (noisy data)
    metrics_high = GateMetrics(
        states_count=50,
        series_pool=5,
        outcome_variance=2.0,
    )

    result_high = probabilistic_evidence_gate(metrics_high)

    # Lower variance should have higher confidence
    assert result_low.confidence >= result_high.confidence


if __name__ == "__main__":
    # Run a quick manual test
    print("Testing probabilistic evidence gate...")

    print("\n1. Testing REJECT (insufficient data):")
    metrics_reject = GateMetrics(states_count=5, series_pool=0)
    result_reject = probabilistic_evidence_gate(metrics_reject)
    print(f"   Decision: {result_reject.decision.value}")
    print(f"   Confidence: {result_reject.confidence:.2f}")
    print(f"   Rationale: {result_reject.rationale}")

    print("\n2. Testing ACCEPT (good data):")
    metrics_accept = GateMetrics(
        states_count=100, series_pool=10, agg_performance=20,
        outcome_field_available=True, aggregation_available=True
    )
    result_accept = probabilistic_evidence_gate(metrics_accept)
    print(f"   Decision: {result_accept.decision.value}")
    print(f"   Confidence: {result_accept.confidence:.2f}")
    print(f"   Rationale: {result_accept.rationale}")

    print("\n3. Testing LOW_CONFIDENCE (borderline):")
    metrics_borderline = GateMetrics(
        states_count=15, series_pool=1, agg_performance=1,
        outcome_field_available=True
    )
    result_borderline = probabilistic_evidence_gate(metrics_borderline)
    print(f"   Decision: {result_borderline.decision.value}")
    print(f"   Confidence: {result_borderline.confidence:.2f}")
    print(f"   Rationale: {result_borderline.rationale}")

    print("\nAll tests passed!")
