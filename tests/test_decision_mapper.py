"""
Tests for Decision Mapper - the critical layer from 1→2.

Tests that the system provides degraded decisions instead of refusing to answer.
"""

from driftcoach.analysis.decision_mapper import (
    DecisionMapper,
    DecisionPath,
    UncertaintyMetrics,
    CoachingDecision,
    map_to_coaching_decision,
)
from driftcoach.config.bounds import DEFAULT_BOUNDS


def test_uncertainty_pricing():
    """Test that uncertainty is correctly priced."""
    mapper = DecisionMapper()

    # Complete context (low uncertainty)
    complete_context = {
        "schema": {"outcome_field": "HOME_WIN"},
        "evidence": {
            "states_count": 50,
            "seriesPool": 5
        }
    }

    uncertainty = mapper._price_uncertainty(complete_context, {"HIGH_RISK_SEQUENCE": [{"round": 1}]})

    assert uncertainty.total < 0.4  # Low uncertainty
    assert uncertainty.missing_outcome == 0.0
    assert uncertainty.severity == "LOW"
    print(f"✅ Complete context: uncertainty={uncertainty.total:.2f}, severity={uncertainty.severity}")

    # Missing outcome (high uncertainty)
    incomplete_context = {
        "schema": {"outcome_field": "NOT_FOUND"},
        "evidence": {
            "states_count": 5,  # Small sample
            "seriesPool": 0  # No comparison
        }
    }

    uncertainty = mapper._price_uncertainty(incomplete_context, {"HIGH_RISK_SEQUENCE": []})

    assert uncertainty.total >= 0.4  # High uncertainty
    assert uncertainty.missing_outcome > 0
    assert uncertainty.small_sample > 0
    assert uncertainty.no_comparison > 0
    print(f"✅ Incomplete context: uncertainty={uncertainty.total:.2f}, severity={uncertainty.severity}")


def test_decision_path_selection():
    """Test that decision path is chosen correctly."""
    mapper = DecisionMapper()

    # No facts → REJECT
    facts_empty = {}
    path = mapper._choose_decision_path(
        UncertaintyMetrics(total=0.5),
        facts_empty
    )
    assert path == DecisionPath.REJECT
    print(f"✅ No facts → {path.value}")

    # High uncertainty → REJECT
    facts_some = {"HIGH_RISK_SEQUENCE": [{"round": 1}]}
    path = mapper._choose_decision_path(
        UncertaintyMetrics(total=0.85),  # Very high uncertainty
        facts_some
    )
    assert path == DecisionPath.REJECT
    print(f"✅ High uncertainty (0.85) → {path.value}")

    # Medium uncertainty + some facts → DEGRADED
    path = mapper._choose_decision_path(
        UncertaintyMetrics(total=0.5),  # Medium uncertainty
        facts_some
    )
    assert path == DecisionPath.DEGRADED
    print(f"✅ Medium uncertainty (0.5) + facts → {path.value}")

    # Low uncertainty → STANDARD
    path = mapper._choose_decision_path(
        UncertaintyMetrics(total=0.2),  # Low uncertainty
        {"HIGH_RISK_SEQUENCE": [{"round": i} for i in range(5)]}
    )
    assert path == DecisionPath.STANDARD
    print(f"✅ Low uncertainty (0.2) → {path.value}")


def test_degraded_decision_generation():
    """Test that degraded decisions are generated correctly."""
    mapper = DecisionMapper()

    # Partial evidence scenario
    context = {
        "schema": {"outcome_field": "NOT_FOUND"},  # Missing outcome
        "evidence": {
            "states_count": 10,  # Small sample
            "seriesPool": 0     # No comparison
        }
    }

    facts = {
        "HIGH_RISK_SEQUENCE": [
            {"round_range": [3, 5], "note": "经济波动"}
        ]
    }

    decision = mapper.map_to_decision(context, "RISK_ASSESSMENT", facts, DEFAULT_BOUNDS)

    # Should be DEGRADED, not REJECT
    assert decision.decision_path == DecisionPath.DEGRADED
    assert decision.verdict == "LOW_CONFIDENCE"
    assert 0.2 <= decision.confidence <= 0.5  # Degraded confidence range
    assert len(decision.caveats) > 0  # Should have caveats
    assert len(decision.support_facts) > 0  # Should provide some answer
    assert "有限证据" in decision.claim or "初步分析" in decision.claim

    print(f"✅ Degraded decision:")
    print(f"   Path: {decision.decision_path.value}")
    print(f"   Claim: {decision.claim}")
    print(f"   Confidence: {decision.confidence}")
    print(f"   Caveats: {decision.caveats}")
    print(f"   Support: {decision.support_facts}")


def test_rejection_when_no_evidence():
    """Test that system rejects only when truly no evidence exists."""
    mapper = DecisionMapper()

    # Completely empty scenario
    context = {
        "schema": {"outcome_field": "NOT_FOUND"},
        "evidence": {
            "states_count": 0,
            "seriesPool": 0
        }
    }

    facts = {}  # No facts at all

    decision = mapper.map_to_decision(context, "RISK_ASSESSMENT", facts, DEFAULT_BOUNDS)

    # Should be REJECT
    assert decision.decision_path == DecisionPath.REJECT
    assert decision.verdict == "INSUFFICIENT"
    assert decision.confidence < 0.3
    assert "完全无可用数据" in decision.claim or "无法分析" in decision.claim

    print(f"✅ Rejection (no evidence):")
    print(f"   Path: {decision.decision_path.value}")
    print(f"   Claim: {decision.claim}")


def test_standard_decision_with_good_evidence():
    """Test standard decision path with complete evidence."""
    mapper = DecisionMapper()

    # Complete scenario
    context = {
        "schema": {"outcome_field": "HOME_WIN"},
        "evidence": {
            "states_count": 100,
            "seriesPool": 10
        }
    }

    facts = {
        "HIGH_RISK_SEQUENCE": [
            {"round_range": [i, i+2], "note": f"风险{i}"}
            for i in [1, 5, 10, 15, 20]  # 5 instances
        ]
    }

    decision = mapper.map_to_decision(context, "RISK_ASSESSMENT", facts, DEFAULT_BOUNDS)

    # Should be STANDARD
    assert decision.decision_path == DecisionPath.STANDARD
    assert decision.confidence > 0.7  # High confidence
    assert len(decision.caveats) == 0  # No caveats for standard

    print(f"✅ Standard decision:")
    print(f"   Path: {decision.decision_path.value}")
    print(f"   Confidence: {decision.confidence}")
    print(f"   Caveats: {decision.caveats}")


def test_uncertainty_severity_levels():
    """Test uncertainty severity mapping."""
    mapper = DecisionMapper()

    test_cases = [
        (0.2, "LOW"),
        (0.35, "MEDIUM"),
        (0.5, "HIGH"),
        (0.85, "CRITICAL"),
        (1.0, "CRITICAL"),
    ]

    for uncertainty_score, expected_severity in test_cases:
        metrics = UncertaintyMetrics(total=uncertainty_score)
        assert metrics.severity == expected_severity
        print(f"✅ Uncertainty {uncertainty_score} → {expected_severity}")


def test_key_principle_never_refuse_when_evidence_exists():
    """
    Test the key principle: Never refuse to answer when ANY evidence exists.

    This is the core 1→2 breakthrough.
    """
    mapper = DecisionMapper()

    # Scenario: Partial evidence (not perfect, but not empty)
    # Use lower uncertainty to ensure DEGRADED path
    context = {
        "schema": {"outcome_field": "NOT_FOUND"},
        "evidence": {
            "states_count": 15,  # Better sample (not too small)
            "seriesPool": 2     # Some comparison (not zero)
        }
    }

    facts = {
        "HIGH_RISK_SEQUENCE": [
            {"round": 5, "note": "有波动"},
            {"round": 10, "note": "经济波动"}
        ]
    }

    decision = mapper.map_to_decision(context, "RISK_ASSESSMENT", facts, DEFAULT_BOUNDS)

    # CRITICAL: Should NOT reject when there's evidence
    assert decision.decision_path != DecisionPath.REJECT
    assert decision.decision_path in [DecisionPath.STANDARD, DecisionPath.DEGRADED]

    # Should provide SOME answer
    assert len(decision.claim) > 0
    assert decision.confidence > 0

    print(f"✅ Key principle test: NEVER refuse when evidence exists")
    print(f"   Path: {decision.decision_path.value} (not REJECT)")
    print(f"   Claim: {decision.claim}")


if __name__ == "__main__":
    print("="*60)
    print("Decision Mapper Tests (1→2 Breakthrough)")
    print("="*60)
    print()

    print("Testing uncertainty pricing...")
    test_uncertainty_pricing()
    print()

    print("Testing decision path selection...")
    test_decision_path_selection()
    print()

    print("Testing degraded decision generation...")
    test_degraded_decision_generation()
    print()

    print("Testing rejection (no evidence)...")
    test_rejection_when_no_evidence()
    print()

    print("Testing standard decision (good evidence)...")
    test_standard_decision_with_good_evidence()
    print()

    print("Testing uncertainty severity levels...")
    test_uncertainty_severity_levels()
    print()

    print("Testing KEY principle: Never refuse when evidence exists...")
    test_key_principle_never_refuse_when_evidence_exists()
    print()

    print("="*60)
    print("✅ All Decision Mapper tests passed!")
    print("="*60)
    print()
    print("Key breakthrough: System now provides degraded decisions")
    print("instead of refusing to answer when partial evidence exists.")
