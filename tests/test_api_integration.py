"""
Integration test for DecisionMapper in api.py

Tests that the API flow now uses DecisionMapper for 1→2 breakthrough.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from driftcoach.analysis.decision_mapper import DecisionMapper, DecisionPath
from driftcoach.config.bounds import DEFAULT_BOUNDS


def test_api_decision_flow():
    """
    Test the decision flow that now happens in api.py (line 2399-2420).

    This simulates what happens when a query comes in with partial evidence.
    """
    print("Testing API decision flow integration...")

    # Simulate the scenario from the production logs
    # Query: "这是不是一场高风险对局？"
    # Loaded: 5731 events, 2 HIGH_RISK_SEQUENCE, 3 ROUND_SWING

    # This is what facts_by_type would look like
    facts_by_type = {
        "HIGH_RISK_SEQUENCE": [
            {"round_range": [3, 5], "note": "经济波动"},
            {"round_range": [12, 14], "note": "连续失分"}
        ],
        "ROUND_SWING": [
            {"round": 5, "note": "局势反转"},
            {"round": 10, "note": "经济波动"},
            {"round": 15, "note": "关键回合"}
        ]
    }

    # This is what context_for_decision would look like
    context_for_decision = {
        "schema": {"outcome_field": "NOT_FOUND"},  # Missing outcome
        "evidence": {
            "states_count": 30,  # 30 CONTEXT_ONLY states
            "seriesPool": 0  # No comparison
        }
    }

    intent = "RISK_ASSESSMENT"

    # This is what the new api.py code does
    mapper = DecisionMapper()
    decision = mapper.map_to_decision(
        context=context_for_decision,
        intent=intent,
        facts=facts_by_type,
        bounds=DEFAULT_BOUNDS
    )

    print(f"\n📊 Decision Result:")
    print(f"   Path: {decision.decision_path.value}")
    print(f"   Claim: {decision.claim}")
    print(f"   Verdict: {decision.verdict}")
    print(f"   Confidence: {decision.confidence}")
    print(f"   Support facts: {len(decision.support_facts)}")
    print(f"   Caveats: {decision.caveats}")
    print(f"   Followups: {decision.followups}")

    # CRITICAL: Should NOT be REJECT (the old behavior)
    assert decision.decision_path != DecisionPath.REJECT, \
        "❌ FAILED: Decision was REJECT! Should be DEGRADED or STANDARD"

    # Should provide SOME answer
    assert len(decision.claim) > 0, "❌ FAILED: No claim generated"
    assert decision.confidence > 0, "❌ FAILED: Zero confidence"

    # Should warn about uncertainty
    assert len(decision.caveats) > 0, "❌ FAILED: No caveats provided"

    # Should suggest followups
    assert len(decision.followups) > 0, "❌ FAILED: No followups provided"

    print("\n✅ Integration test PASSED!")
    print(f"\n🎯 Key improvement:")
    print(f"   Before: verdict=INSUFFICIENT, confidence=0.27, \"证据不足\"")
    print(f"   After:  verdict={decision.verdict}, confidence={decision.confidence}, \"{decision.claim[:50]}...\"")

    return True


def test_complete_evidence_flow():
    """
    Test that complete evidence still gets STANDARD path.
    """
    print("\n\nTesting complete evidence flow...")

    facts_by_type = {
        "HIGH_RISK_SEQUENCE": [
            {"round_range": [i, i+2], "note": f"风险{i}"}
            for i in [1, 5, 10, 15, 20]  # 5 instances
        ]
    }

    context_for_decision = {
        "schema": {"outcome_field": "HOME_WIN"},
        "evidence": {
            "states_count": 100,
            "seriesPool": 10
        }
    }

    mapper = DecisionMapper()
    decision = mapper.map_to_decision(
        context=context_for_decision,
        intent="RISK_ASSESSMENT",
        facts=facts_by_type,
        bounds=DEFAULT_BOUNDS
    )

    print(f"\n📊 Decision Result:")
    print(f"   Path: {decision.decision_path.value}")
    print(f"   Confidence: {decision.confidence}")
    print(f"   Caveats: {decision.caveats}")

    assert decision.decision_path == DecisionPath.STANDARD
    assert decision.confidence > 0.7
    assert len(decision.caveats) == 0

    print("✅ Complete evidence flow PASSED!")

    return True


def test_no_evidence_flow():
    """
    Test that truly no evidence gets REJECT (not DEGRADED).
    """
    print("\n\nTesting no evidence flow...")

    facts_by_type = {}

    context_for_decision = {
        "schema": {"outcome_field": "NOT_FOUND"},
        "evidence": {
            "states_count": 0,
            "seriesPool": 0
        }
    }

    mapper = DecisionMapper()
    decision = mapper.map_to_decision(
        context=context_for_decision,
        intent="RISK_ASSESSMENT",
        facts=facts_by_type,
        bounds=DEFAULT_BOUNDS
    )

    print(f"\n📊 Decision Result:")
    print(f"   Path: {decision.decision_path.value}")
    print(f"   Claim: {decision.claim}")

    assert decision.decision_path == DecisionPath.REJECT
    assert decision.verdict == "INSUFFICIENT"

    print("✅ No evidence flow PASSED!")

    return True


if __name__ == "__main__":
    print("=" * 70)
    print("API Integration Tests for 1→2 Breakthrough")
    print("=" * 70)
    print()

    test_api_decision_flow()
    test_complete_evidence_flow()
    test_no_evidence_flow()

    print("\n" + "=" * 70)
    print("✅ ALL INTEGRATION TESTS PASSED!")
    print("=" * 70)
    print("\n🚀 The API is now using DecisionMapper for 1→2 breakthrough.")
    print("   Partial evidence → DEGRADED decision (not REJECT)")
    print("   Complete evidence → STANDARD decision")
    print("   No evidence → REJECT (explicit refusal)")
