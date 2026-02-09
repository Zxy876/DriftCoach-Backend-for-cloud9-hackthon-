"""
Tests for Spec Implementation

验证 Spec 收缩可见性是否正常工作
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from driftcoach.specs.spec_schema import (
    SpecFocus,
    SpecRecognizer,
    ECON_SPEC,
    RISK_SPEC,
    MAP_SPEC,
    PLAYER_SPEC,
    SUMMARY_SPEC,
    MOMENTUM_SPEC,
)


def test_intent_to_spec_mapping():
    """测试 intent → spec 映射"""
    print("测试 Intent → Spec 映射...")
    print()

    test_cases = [
        ("RISK_ASSESSMENT", RISK_SPEC),
        ("ECONOMIC_COUNTERFACTUAL", ECON_SPEC),
        ("MAP_WEAK_POINT", MAP_SPEC),
        ("PLAYER_REVIEW", PLAYER_SPEC),
        ("MATCH_SUMMARY", SUMMARY_SPEC),
        ("MOMENTUM_ANALYSIS", MOMENTUM_SPEC),
    ]

    for intent, expected_spec in test_cases:
        spec = SpecRecognizer.recognize_spec(intent)
        assert spec == expected_spec, f"Intent {intent} 映射错误"
        print(f"✅ {intent} → {spec.focus.value}_SPEC")

    print()


def test_spec_visibility_reduction():
    """测试 spec 收缩可见性"""
    print("测试 Spec 收缩可见性...")
    print()

    # 模拟全局 facts 池
    all_facts = [
        {"fact_type": "HIGH_RISK_SEQUENCE", "round": 5, "note": "R3-R5 风险"},
        {"fact_type": "HIGH_RISK_SEQUENCE", "round": 15, "note": "R12-R14 风险"},
        {"fact_type": "ROUND_SWING", "round": 10, "note": "R10 反转"},
        {"fact_type": "FORCE_BUY_ROUND", "round": 3, "note": "强起失败"},
        {"fact_type": "ECO_COLLAPSE_SEQUENCE", "round": 8, "note": "经济崩盘"},
        {"fact_type": "PLAYER_IMPACT_STAT", "player": "X", "note": "KD 0.8"},
        {"fact_type": "OBJECTIVE_LOSS_CHAIN", "round": 15, "note": "目标丢失链"},
    ]

    print(f"全局 facts 池: {len(all_facts)} 个 facts")
    print(f"  Types: {[f['fact_type'] for f in all_facts]}")
    print()

    # 测试不同 spec 看到的 facts
    intents = [
        ("RISK_ASSESSMENT", "RISK"),
        ("ECONOMIC_COUNTERFACTUAL", "ECON"),
        ("MAP_WEAK_POINT", "MAP"),
        ("PLAYER_REVIEW", "PLAYER"),
    ]

    for intent, focus_name in intents:
        spec_facts = SpecRecognizer.filter_facts_by_spec(intent, all_facts)
        fact_types = [f['fact_type'] for f in spec_facts]

        print(f"{intent} ({focus_name}_SPEC):")
        print(f"  看到的 facts: {len(spec_facts)} 个")
        print(f"  Types: {fact_types}")
        print()

    # 验证不同 spec 看到的 facts 不同
    risk_facts = SpecRecognizer.filter_facts_by_spec("RISK_ASSESSMENT", all_facts)
    econ_facts = SpecRecognizer.filter_facts_by_spec("ECONOMIC_COUNTERFACTUAL", all_facts)
    player_facts = SpecRecognizer.filter_facts_by_spec("PLAYER_REVIEW", all_facts)

    risk_types = [f['fact_type'] for f in risk_facts]
    econ_types = [f['fact_type'] for f in econ_facts]
    player_types = [f['fact_type'] for f in player_facts]

    assert risk_types != econ_types, "RISK 和 ECON 应该看到不同的 facts"
    assert econ_types != player_types, "ECON 和 PLAYER 应该看到不同的 facts"

    print("✅ 不同 spec 看到的 facts 不同（可见性收缩成功）")
    print()


def test_spec_budget():
    """测试 spec budget 限制"""
    print("测试 Spec Budget...")
    print()

    # 创建大量 facts
    all_facts = [
        {"fact_type": "HIGH_RISK_SEQUENCE", "round": i, "note": f"风险{i}"}
        for i in range(20)  # 20 个 facts
    ]

    print(f"全局 facts: {len(all_facts)} 个")
    print()

    # 测试 RISK_SPEC 的 budget 限制
    risk_facts = SpecRecognizer.filter_facts_by_spec("RISK_ASSESSMENT", all_facts)

    print(f"RISK_SPEC.max_facts_total = {RISK_SPEC.budget.max_facts_total}")
    print(f"RISK_SPEC 实际返回: {len(risk_facts)} 个 facts")

    assert len(risk_facts) <= RISK_SPEC.budget.max_facts_total, "超出 budget"
    print("✅ Budget 限制生效")
    print()


def test_unknown_intent_fallback():
    """测试未知 intent 回退到 SUMMARY_SPEC"""
    print("测试未知 Intent 回退...")
    print()

    unknown_intent = "UNKNOWN_INTENT"
    spec = SpecRecognizer.recognize_spec(unknown_intent)

    assert spec == SUMMARY_SPEC, "未知 intent 应该回退到 SUMMARY_SPEC"
    print(f"✅ 未知 intent → {spec.focus.value}_SUMMARY")
    print()


def test_spec_output_contract():
    """测试 spec 的输出契约"""
    print("测试 Spec Output Contract...")
    print()

    specs = [
        ("ECON", ECON_SPEC),
        ("RISK", RISK_SPEC),
        ("MAP", MAP_SPEC),
        ("PLAYER", PLAYER_SPEC),
        ("SUMMARY", SUMMARY_SPEC),
        ("MOMENTUM", MOMENTUM_SPEC),
    ]

    for name, spec in specs:
        print(f"{name}_SPEC:")
        print(f"  Standard 置信度门槛: {spec.output_contract.standard_min_confidence}")
        print(f"  Degraded 不确定性上限: {spec.output_contract.degraded_max_uncertainty}")
        print(f"  Max Facts: {spec.budget.max_facts_total}")
        print()

    print("✅ 所有 Spec 的 Output Contract 已定义")
    print()


if __name__ == "__main__":
    print("=" * 70)
    print("Spec Implementation Tests")
    print("=" * 70)
    print()

    test_intent_to_spec_mapping()
    test_spec_visibility_reduction()
    test_spec_budget()
    test_unknown_intent_fallback()
    test_spec_output_contract()

    print("=" * 70)
    print("✅ All Spec Tests Passed!")
    print("=" * 70)
    print()
    print("🎯 关键突破:")
    print("   - 不同 query 看到不同的 facts 子空间")
    print("   - Spec 收缩了可见性（search space reduction）")
    print("   - 解决了 F(X1)=y, F(X2)=y 的问题")
    print()
    print("📁 相关文件:")
    print("   - driftcoach/specs/spec_schema.py")
    print("   - SPEC_DESIGN.md")
    print("   - SPEC_IMPLEMENTATION_SUMMARY.md")
