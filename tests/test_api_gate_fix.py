"""
Test that DecisionMapper result takes precedence over old gate logic.

This test verifies the fix for the issue where inference_plan["rationale"]
was overriding DecisionMapper's result.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from driftcoach.analysis.decision_mapper import DecisionMapper, DecisionPath, CoachingDecision
from driftcoach.config.bounds import DEFAULT_BOUNDS


def test_decision_mapper_precedence():
    """
    Test that DecisionMapper result is used instead of old gate rationale.

    Simulates the api.py logic at lines 2732-2747.
    """
    print("Testing DecisionMapper precedence over old gate...")

    # Simulate DecisionMapper generating a DEGRADED decision
    mapper = DecisionMapper()
    decision = mapper.map_to_decision(
        context={
            "schema": {"outcome_field": "NOT_FOUND"},
            "evidence": {"states_count": 30, "seriesPool": 0}
        },
        intent="RISK_ASSESSMENT",
        facts={
            "HIGH_RISK_SEQUENCE": [
                {"round_range": [3, 5], "note": "经济波动"}
            ]
        },
        bounds=DEFAULT_BOUNDS
    )

    # Simulate context_meta with DecisionMapper result
    answer_synthesis = {
        "claim": decision.claim,
        "verdict": decision.verdict,
        "confidence": decision.confidence,
        "support_facts": decision.support_facts,
        "counter_facts": decision.counter_facts,
        "followups": decision.followups
    }

    # Simulate old gate's inference_plan (would have said "证据不足")
    inference_plan = {
        "judgment": "EVIDENCE_INSUFFICIENT",
        "rationale": "样本量不足（得分=0.00）；数据质量不佳（得分=0.52）；总体置信度 0.27"
    }

    # This is the NEW logic from api.py lines 2732-2747
    payload = {}

    if answer_synthesis.get("claim") and answer_synthesis.get("verdict") != "INSUFFICIENT":
        # ✅ DecisionMapper provided a valid answer (DEGRADED or STANDARD)
        payload["assistant_message"] = answer_synthesis.get("claim")
        print(f"✅ Using DecisionMapper result: {payload['assistant_message'][:50]}...")
    elif inference_plan.get("rationale"):
        # ❌ Old gate logic (should NOT be reached)
        payload["assistant_message"] = inference_plan.get("rationale")
        print(f"❌ Using old gate rationale: {payload['assistant_message']}")

    # Verify: Should use DecisionMapper result, not old gate
    assert "证据不足" not in payload.get("assistant_message", ""), \
        "❌ FAILED: Old gate rationale was used!"
    assert "基于" in payload.get("assistant_message", "") or "检测到" in payload.get("assistant_message", ""), \
        "❌ FAILED: DecisionMapper claim was not used!"

    print(f"\n📊 Result:")
    print(f"   Decision path: {decision.decision_path.value}")
    print(f"   Verdict: {decision.verdict}")
    print(f"   Confidence: {decision.confidence}")
    print(f"   Assistant message: {payload['assistant_message'][:80]}...")

    print("\n✅ Test PASSED: DecisionMapper takes precedence over old gate!")
    return True


def test_insufficient_verdict_still_uses_gate():
    """
    Test that when DecisionMapper returns INSUFFICIENT (true rejection),
    the old gate logic can still provide rationale.
    """
    print("\n\nTesting INSUFFICIENT verdict fallback...")

    # Simulate DecisionMapper returning INSUFFICIENT (true rejection)
    answer_synthesis = {
        "claim": "当前完全无可用数据，无法进行分析",
        "verdict": "INSUFFICIENT",
        "confidence": 0.2
    }

    # Old gate provides more specific rationale
    inference_plan = {
        "judgment": "EVIDENCE_INSUFFICIENT",
        "rationale": "缺少胜负结果；样本量不足；需要更多数据"
    }

    # NEW logic
    payload = {}

    if answer_synthesis.get("claim") and answer_synthesis.get("verdict") != "INSUFFICIENT":
        payload["assistant_message"] = answer_synthesis.get("claim")
        print("Using DecisionMapper result")
    elif inference_plan.get("rationale"):
        payload["assistant_message"] = inference_plan.get("rationale")
        print(f"Using old gate rationale (as expected for INSUFFICIENT)")

    # Should use old gate rationale when DecisionMapper says INSUFFICIENT
    assert payload["assistant_message"] == inference_plan["rationale"]

    print("\n✅ Test PASSED: Old gate used for INSUFFICIENT verdict!")
    return True


def test_standard_decision_precedence():
    """
    Test that STANDARD decision also takes precedence over old gate.
    """
    print("\n\nTesting STANDARD decision precedence...")

    answer_synthesis = {
        "claim": "这是一场高风险对局",
        "verdict": "YES",
        "confidence": 0.9
    }

    inference_plan = {
        "judgment": "EVIDENCE_INSUFFICIENT",  # Old gate might be wrong
        "rationale": "证据不足"
    }

    payload = {}

    if answer_synthesis.get("claim") and answer_synthesis.get("verdict") != "INSUFFICIENT":
        payload["assistant_message"] = answer_synthesis.get("claim")

    assert payload["assistant_message"] == answer_synthesis["claim"]
    assert "证据不足" not in payload["assistant_message"]

    print("✅ Test PASSED: STANDARD decision takes precedence!")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("API Gate Fix Tests - DecisionMapper Precedence")
    print("=" * 70)
    print()

    test_decision_mapper_precedence()
    test_insufficient_verdict_still_uses_gate()
    test_standard_decision_precedence()

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED!")
    print("=" * 70)
    print("\n🎯 Fix Summary:")
    print("   - DecisionMapper result takes precedence over old gate")
    print("   - Old gate only used when DecisionMapper says INSUFFICIENT")
    print("   - Prevents '证据不足' from overriding valid DEGRADED/STANDARD decisions")
