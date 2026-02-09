"""
Tests for divide-and-conquer answer synthesizer.
"""

import pytest
from driftcoach.analysis.synthesizer_router import AnswerSynthesizer
from driftcoach.analysis.intent_handlers import (
    RiskAssessmentHandler,
    EconomicCounterfactualHandler,
    MomentumAnalysisHandler,
)
from driftcoach.analysis.answer_synthesizer import AnswerInput
from driftcoach.config.bounds import DEFAULT_BOUNDS, SystemBounds


def test_risk_assessment_high_risk():
    """Test RISK_ASSESSMENT with high risk facts."""
    inp = AnswerInput(
        question="这场比赛风险高吗？",
        intent="RISK_ASSESSMENT",
        required_facts=["HIGH_RISK_SEQUENCE", "ROUND_SWING"],
        facts={
            "HIGH_RISK_SEQUENCE": [
                {"round_range": [1, 3], "note": "经济崩盘"},
                {"round_range": [10, 12], "note": "强起失败"},
            ],
            "ROUND_SWING": [{"game_index": 1}],
        },
        series_id="series-1",
    )

    synthesizer = AnswerSynthesizer()
    result = synthesizer.synthesize(inp)

    assert result.verdict == "YES"
    assert result.confidence == 0.9
    assert "高风险" in result.claim
    assert len(result.support_facts) <= DEFAULT_BOUNDS.max_support_facts


def test_risk_assessment_low_confidence():
    """Test RISK_ASSESSMENT with limited evidence (degraded decision)."""
    inp = AnswerInput(
        question="这场比赛风险高吗？",
        intent="RISK_ASSESSMENT",
        required_facts=["HIGH_RISK_SEQUENCE"],
        facts={
            "HIGH_RISK_SEQUENCE": [
                {"round_range": [5, 7], "note": "经济波动"},
            ],
            "ROUND_SWING": [],
        },
        series_id="series-1",
    )

    synthesizer = AnswerSynthesizer()
    result = synthesizer.synthesize(inp)

    assert result.verdict in ["LOW_CONFIDENCE", "INSUFFICIENT"]
    assert result.confidence < 0.5
    # Should provide some answer even with limited evidence


def test_economic_counterfactual_force_buy():
    """Test ECONOMIC_COUNTERFACTUAL with force buy evidence."""
    inp = AnswerInput(
        question="保枪是否更好？",
        intent="ECONOMIC_COUNTERFACTUAL",
        required_facts=["FORCE_BUY_ROUND", "ECO_COLLAPSE_SEQUENCE"],
        facts={
            "FORCE_BUY_ROUND": [
                {"round": 5, "note": "强起"},
            ],
            "ECO_COLLAPSE_SEQUENCE": [
                {"round_range": [5, 7], "note": "经济崩盘"},
            ],
            "FULL_BUY_ROUND": [],
        },
        series_id="series-1",
    )

    synthesizer = AnswerSynthesizer()
    result = synthesizer.synthesize(inp)

    assert result.verdict == "YES"
    assert "强起" in result.claim or "保枪" in result.claim
    assert result.confidence > 0.7


def test_momentum_analysis_with_swings():
    """Test MOMENTUM_ANALYSIS with swing evidence."""
    inp = AnswerInput(
        question="比赛有反转吗？",
        intent="MOMENTUM_ANALYSIS",
        required_facts=["ROUND_SWING"],
        facts={
            "ROUND_SWING": [
                {"game_index": 1, "round": 5, "note": "逆转"},
                {"game_index": 2, "round": 10, "note": "逆转"},
            ],
        },
        series_id="series-1",
    )

    synthesizer = AnswerSynthesizer()
    result = synthesizer.synthesize(inp)

    assert result.verdict == "YES"
    assert "反转" in result.claim
    assert len(result.support_facts) > 0


def test_momentum_analysis_no_swings():
    """Test MOMENTUM_ANALYSIS without swing evidence."""
    inp = AnswerInput(
        question="比赛有反转吗？",
        intent="MOMENTUM_ANALYSIS",
        required_facts=["ROUND_SWING"],
        facts={
            "ROUND_SWING": [],
        },
        series_id="series-1",
    )

    synthesizer = AnswerSynthesizer()
    result = synthesizer.synthesize(inp)

    assert result.verdict == "NO"
    assert "未发现" in result.claim or "没有" in result.claim


def test_bounds_enforcement():
    """Test that bounds are enforced on outputs."""
    inp = AnswerInput(
        question="这场比赛风险高吗？",
        intent="RISK_ASSESSMENT",
        required_facts=["HIGH_RISK_SEQUENCE"],
        facts={
            "HIGH_RISK_SEQUENCE": [
                {"round_range": [i, i+2], "note": f"风险{i}"}
                for i in range(10)  # More than max_support_facts
            ],
        },
        series_id="series-1",
    )

    # Test with restrictive bounds
    tight_bounds = SystemBounds(
        max_sub_intents=3,
        max_findings_per_intent=2,
        max_findings_total=5,
        max_support_facts=2,  # Only 2 support facts
        max_counter_facts=3,
        max_followup_questions=3,
    )

    synthesizer = AnswerSynthesizer()
    result = synthesizer.synthesize(inp, bounds=tight_bounds)

    # Should enforce max_support_facts
    assert len(result.support_facts) <= 2


def test_handler_routing():
    """Test that intents are routed to correct handlers."""
    synthesizer = AnswerSynthesizer()

    # Test RISK_ASSESSMENT routing
    risk_inp = AnswerInput(
        question="风险高吗？",
        intent="RISK_ASSESSMENT",
        required_facts=[],
        facts={},
        series_id="series-1",
    )

    # Check that RiskAssessmentHandler is used
    for handler in synthesizer.handlers:
        if handler.can_handle("RISK_ASSESSMENT"):
            assert isinstance(handler, RiskAssessmentHandler)
            break

    # Test ECONOMIC_COUNTERFACTUAL routing
    econ_inp = AnswerInput(
        question="经济决策？",
        intent="ECONOMIC_COUNTERFACTUAL",
        required_facts=[],
        facts={},
        series_id="series-1",
    )

    for handler in synthesizer.handlers:
        if handler.can_handle("ECONOMIC_COUNTERFACTUAL"):
            assert isinstance(handler, EconomicCounterfactualHandler)
            break


def test_fallback_handler():
    """Test fallback handler for unknown intents."""
    inp = AnswerInput(
        question="未知意图",
        intent="UNKNOWN_INTENT",
        required_facts=[],
        facts={
            "SOME_FACT": [{"note": "some data"}],
        },
        series_id="series-1",
    )

    synthesizer = AnswerSynthesizer()
    result = synthesizer.synthesize(inp)

    # Should provide degraded answer
    assert result.verdict in ["LOW_CONFIDENCE", "INSUFFICIENT"]
    assert result.confidence <= 0.35


def test_handler_independence():
    """Test that handlers can be tested independently."""
    # Test RiskAssessmentHandler in isolation
    handler = RiskAssessmentHandler()

    assert handler.can_handle("RISK_ASSESSMENT") is True
    assert handler.can_handle("ECONOMIC_COUNTERFACTUAL") is False

    # Test with context
    from driftcoach.analysis.intent_handlers import HandlerContext

    ctx = HandlerContext(
        input=AnswerInput(
            question="测试",
            intent="RISK_ASSESSMENT",
            required_facts=[],
            facts={"HIGH_RISK_SEQUENCE": [{"round": 1}]},
            series_id="series-1",
        ),
        bounds=DEFAULT_BOUNDS,
        intent="RISK_ASSESSMENT"
    )

    result = handler.process(ctx)
    assert result is not None
    assert isinstance(result.verdict, str)


if __name__ == "__main__":
    print("Testing divide-and-conquer synthesizer...")

    test_risk_assessment_high_risk()
    print("✅ High risk assessment")

    test_risk_assessment_low_confidence()
    print("✅ Low confidence with limited evidence")

    test_economic_counterfactual_force_buy()
    print("✅ Economic counterfactual")

    test_momentum_analysis_with_swings()
    print("✅ Momentum analysis with swings")

    test_momentum_analysis_no_swings()
    print("✅ Momentum analysis without swings")

    test_bounds_enforcement()
    print("✅ Bounds enforcement")

    test_handler_routing()
    print("✅ Handler routing")

    test_fallback_handler()
    print("✅ Fallback handler")

    test_handler_independence()
    print("✅ Handler independence")

    print("\n✅ All divide-and-conquer tests passed!")
