"""
Quick test to diagnose why Spec-based handlers aren't working
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from driftcoach.analysis.answer_synthesizer import AnswerInput, synthesize_answer
from driftcoach.config.bounds import DEFAULT_BOUNDS

# Test 1: RISK_ASSESSMENT with HIGH_RISK_SEQUENCE facts
print("=" * 70)
print("Test 1: RISK_ASSESSMENT with risk facts")
print("=" * 70)

risk_input = AnswerInput(
    question="这是不是一场高风险对局？",
    intent="RISK_ASSESSMENT",
    required_facts=["HIGH_RISK_SEQUENCE", "ROUND_SWING"],
    facts={
        "HIGH_RISK_SEQUENCE": [
            {"fact_type": "HIGH_RISK_SEQUENCE", "round_range": [3, 5], "note": "R3-R5 经济波动"},
            {"fact_type": "HIGH_RISK_SEQUENCE", "round_range": [12, 14], "note": "R12-R14 连续失分"},
        ],
        "ROUND_SWING": [
            {"fact_type": "ROUND_SWING", "round": 5, "note": "R5 局势反转"},
            {"fact_type": "ROUND_SWING", "round": 10, "note": "R10 局势反转"},
            {"fact_type": "ROUND_SWING", "round": 15, "note": "R15 局势反转"},
        ],
    },
    series_id="test_series",
)

result = synthesize_answer(risk_input, bounds=DEFAULT_BOUNDS)
print(f"Claim: {result.claim}")
print(f"Verdict: {result.verdict}")
print(f"Confidence: {result.confidence}")
print(f"Support facts: {len(result.support_facts)}")
print()

# Test 2: ECONOMIC_COUNTERFACTUAL with econ facts
print("=" * 70)
print("Test 2: ECONOMIC_COUNTERFACTUAL with econ facts")
print("=" * 70)

econ_input = AnswerInput(
    question="经济决策有什么问题？",
    intent="ECONOMIC_COUNTERFACTUAL",
    required_facts=["FORCE_BUY_ROUND", "ECO_COLLAPSE_SEQUENCE"],
    facts={
        "FORCE_BUY_ROUND": [
            {"fact_type": "FORCE_BUY_ROUND", "round": 3, "note": "强起失败"},
        ],
        "ECO_COLLAPSE_SEQUENCE": [
            {"fact_type": "ECO_COLLAPSE_SEQUENCE", "round_range": [8, 10], "note": "经济崩盘"},
        ],
    },
    series_id="test_series",
)

result = synthesize_answer(econ_input, bounds=DEFAULT_BOUNDS)
print(f"Claim: {result.claim}")
print(f"Verdict: {result.verdict}")
print(f"Confidence: {result.confidence}")
print(f"Support facts: {len(result.support_facts)}")
print()

# Test 3: Empty facts (should trigger DEGRADED path)
print("=" * 70)
print("Test 3: RISK_ASSESSMENT with no facts (DEGRADED path)")
print("=" * 70)

empty_input = AnswerInput(
    question="这是不是一场高风险对局？",
    intent="RISK_ASSESSMENT",
    required_facts=["HIGH_RISK_SEQUENCE"],
    facts={},
    series_id="test_series",
)

result = synthesize_answer(empty_input, bounds=DEFAULT_BOUNDS)
print(f"Claim: {result.claim}")
print(f"Verdict: {result.verdict}")
print(f"Confidence: {result.confidence}")
print()

print("=" * 70)
print("✅ All tests completed")
print("=" * 70)
