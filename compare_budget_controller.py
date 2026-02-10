#!/usr/bin/env python3
"""
L5 BudgetController 对照验证

对比：
1. WITHOUT BudgetController（使用所有 facts）
2. WITH BudgetController（理性停止）

关键维度：
- facts 使用数量
- confidence 曲线
- verdict
- followups 聚焦度

目标：验证 BudgetController 是否让"停止"变得有理有据，而不是随机。
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from driftcoach.analysis.intent_handlers import RiskAssessmentHandler
from driftcoach.analysis.answer_synthesizer import AnswerInput
from driftcoach.config.bounds import DEFAULT_BOUNDS


def create_test_facts():
    """Create test facts for comparison."""
    return {
        "HIGH_RISK_SEQUENCE": [
            {"fact_type": "HIGH_RISK_SEQUENCE", "round_range": [1, 3], "note": "R1-R3 经济波动"},
            {"fact_type": "HIGH_RISK_SEQUENCE", "round_range": [10, 12], "note": "R10-R12 连续失分"},
            {"fact_type": "HIGH_RISK_SEQUENCE", "round_range": [20, 22], "note": "R20-R22 高风险"},
            {"fact_type": "HIGH_RISK_SEQUENCE", "round_range": [28, 30], "note": "R28-R30 风险"},
        ],
        "ROUND_SWING": [
            {"fact_type": "ROUND_SWING", "round": 5, "note": "R5 局势反转"},
            {"fact_type": "ROUND_SWING", "round": 8, "note": "R8 反转"},
            {"fact_type": "ROUND_SWING", "round": 11, "note": "R11 反转"},
            {"fact_type": "ROUND_SWING", "round": 15, "note": "R15 反转"},
            {"fact_type": "ROUND_SWING", "round": 18, "note": "R18 反转"},
            {"fact_type": "ROUND_SWING", "round": 21, "note": "R21 反转"},
        ],
    }


def run_without_budget_controller():
    """Run WITHOUT BudgetController (use all facts)."""
    print("=" * 70)
    print("📊 Test 1: WITHOUT BudgetController")
    print("=" * 70)
    print()

    # Temporarily disable BudgetController
    os.environ["BUDGET_CONTROLLER_ENABLED"] = "false"

    # Reimport to pick up the environment variable
    import importlib
    from driftcoach.analysis import intent_handlers
    importlib.reload(intent_handlers)

    handler = intent_handlers.RiskAssessmentHandler()

    # Create input with test facts
    input_data = AnswerInput(
        question="这是不是一场高风险对局？",
        intent="RISK_ASSESSMENT",
        required_facts=["HIGH_RISK_SEQUENCE"],
        facts=create_test_facts(),
        series_id="test_series",
    )

    ctx = intent_handlers.HandlerContext(
        input=input_data,
        bounds=DEFAULT_BOUNDS,
        intent="RISK_ASSESSMENT"
    )

    result = handler.process(ctx)

    # Extract metrics
    metrics = {
        "facts_used": len(result.support_facts) + len(result.counter_facts),
        "confidence": result.confidence,
        "verdict": result.verdict,
        "claim": result.claim,
        "followups": result.followups,
        "support_facts": result.support_facts,
    }

    print(f"📊 Facts Used: {metrics['facts_used']}")
    print(f"📊 Confidence: {metrics['confidence']}")
    print(f"📊 Verdict: {metrics['verdict']}")
    print(f"📊 Claim: {metrics['claim']}")
    print(f"📊 Support Facts ({len(metrics['support_facts'])}):")
    for i, fact in enumerate(metrics['support_facts'][:5], 1):
        print(f"   {i}. {fact}")
    print(f"📊 Followups ({len(metrics['followups'])}):")
    for i, followup in enumerate(metrics['followups'][:3], 1):
        print(f"   {i}. {followup}")
    print()

    return metrics


def run_with_budget_controller():
    """Run WITH BudgetController (rational stopping)."""
    print("=" * 70)
    print("📊 Test 2: WITH BudgetController")
    print("=" * 70)
    print()

    # Enable BudgetController
    os.environ["BUDGET_CONTROLLER_ENABLED"] = "true"

    # Reimport to pick up the environment variable
    import importlib
    from driftcoach.analysis import intent_handlers
    importlib.reload(intent_handlers)

    handler = intent_handlers.RiskAssessmentHandler()

    # Create input with test facts
    input_data = AnswerInput(
        question="这是不是一场高风险对局？",
        intent="RISK_ASSESSMENT",
        required_facts=["HIGH_RISK_SEQUENCE"],
        facts=create_test_facts(),
        series_id="test_series",
    )

    ctx = intent_handlers.HandlerContext(
        input=input_data,
        bounds=DEFAULT_BOUNDS,
        intent="RISK_ASSESSMENT"
    )

    result = handler.process(ctx)

    # Extract metrics
    metrics = {
        "facts_used": len(result.support_facts) + len(result.counter_facts),
        "confidence": result.confidence,
        "verdict": result.verdict,
        "claim": result.claim,
        "followups": result.followups,
        "support_facts": result.support_facts,
    }

    print(f"📊 Facts Used: {metrics['facts_used']}")
    print(f"📊 Confidence: {metrics['confidence']}")
    print(f"📊 Verdict: {metrics['verdict']}")
    print(f"📊 Claim: {metrics['claim']}")
    print(f"📊 Support Facts ({len(metrics['support_facts'])}):")
    for i, fact in enumerate(metrics['support_facts'][:5], 1):
        print(f"   {i}. {fact}")
    print(f"📊 Followups ({len(metrics['followups'])}):")
    for i, followup in enumerate(metrics['followups'][:3], 1):
        print(f"   {i}. {followup}")
    print()

    return metrics


def compare_results(without_bc, with_bc):
    """Compare results across 4 key dimensions."""
    print("=" * 70)
    print("🔍 对照分析：4 个关键维度")
    print("=" * 70)
    print()

    # Dimension 1: Facts Used
    print("维度 1: 使用的 Facts 数")
    print("-" * 70)
    print(f"  WITHOUT BudgetController: {without_bc['facts_used']} facts")
    print(f"  WITH BudgetController:    {with_bc['facts_used']} facts")

    if with_bc['facts_used'] < without_bc['facts_used']:
        saved = without_bc['facts_used'] - with_bc['facts_used']
        efficiency = (saved / without_bc['facts_used']) * 100
        print(f"  ✅ 节省: {saved} facts ({efficiency:.1f}% 效率提升)")
    else:
        print(f"  ⚠️  未节省 facts")

    print()

    # Dimension 2: Confidence (KEY)
    print("维度 2: Confidence 曲线 (最关键)")
    print("-" * 70)
    print(f"  WITHOUT BudgetController: {without_bc['confidence']}")
    print(f"  WITH BudgetController:    {with_bc['confidence']}")

    # Check if confidence achieved target (>= 0.7)
    if with_bc['confidence'] >= 0.7:
        print(f"  ✅ WITH BC: Confidence 达到目标 (0.7)")
    elif abs(with_bc['confidence'] - 0.7) < 0.15:
        print(f"  ⚠️  WITH BC: Confidence 接近目标 (0.7 ± 0.15)")
    else:
        print(f"  ❌ WITH BC: Confidence 未达到目标 (0.7)")

    print()

    # Dimension 3: Verdict
    print("维度 3: Verdict")
    print("-" * 70)
    print(f"  WITHOUT BudgetController: {without_bc['verdict']}")
    print(f"  WITH BudgetController:    {with_bc['verdict']}")

    if without_bc['verdict'] == with_bc['verdict']:
        print(f"  ✅ Verdict 一致（BudgetController 未改变结论）")
    else:
        print(f"  ⚠️  Verdict 不同（需要进一步分析）")

    print()

    # Dimension 4: Followups Focus (KEY)
    print("维度 4: Followups 聚焦度 (最关键)")
    print("-" * 70)
    print(f"  WITHOUT BudgetController: {len(without_bc['followups'])} followups")
    print(f"  WITH BudgetController:    {len(with_bc['followups'])} followups")

    if with_bc['followups']:
        print(f"  WITH BC followups:")
        for i, followup in enumerate(with_bc['followups'][:3], 1):
            print(f"    {i}. {followup}")
    else:
        print(f"  WITH BC: 无 followups（结论明确）")

    if len(with_bc['followups']) <= len(without_bc['followups']):
        print(f"  ✅ WITH BC: Followups 更聚焦（或相同）")
    else:
        print(f"  ⚠️  WITH BC: Followups 更多（可能不够聚焦）")

    print()


def main():
    """Run comparison test."""
    print("=" * 70)
    print("🔍 L5 BudgetController 对照验证")
    print("=" * 70)
    print()
    print("问题: \"这是不是一场高风险对局？\"")
    print("目标: 验证 BudgetController 是否让\"停止\"变得有理有据")
    print()

    # Run tests
    without_bc = run_without_budget_controller()
    with_bc = run_with_budget_controller()

    # Compare
    compare_results(without_bc, with_bc)

    # Final verdict
    print("=" * 70)
    print("🎯 验证结论")
    print("=" * 70)
    print()

    checks = []

    # Check 1: Confidence stability
    # 如果 confidence >= 0.7，认为已达到或超过目标
    if with_bc['confidence'] >= 0.7:
        checks.append(("✅", f"Confidence 达到目标 (0.7), 实际: {with_bc['confidence']}", True))
    else:
        checks.append(("❌", f"Confidence 未达到目标 (0.7), 实际: {with_bc['confidence']}", False))

    # Check 2: Efficiency
    if with_bc['facts_used'] < without_bc['facts_used']:
        checks.append(("✅", "节省 facts（效率提升）", True))
    else:
        checks.append(("⚠️", "未节省 facts", False))

    # Check 3: Verdict consistency
    if without_bc['verdict'] == with_bc['verdict']:
        checks.append(("✅", "Verdict 一致（未改变结论）", True))
    else:
        checks.append(("❌", "Verdict 改变（需要分析）", False))

    # Check 4: Followup focus
    if len(with_bc['followups']) <= len(without_bc['followups']):
        checks.append(("✅", "Followups 聚焦（或更少）", True))
    else:
        checks.append(("⚠️", "Followups 增加", False))

    for icon, message, passed in checks:
        print(f"{icon} {message}")

    print()

    all_passed = all(check[2] for check in checks)

    if all_passed:
        print("🎉 验证通过：BudgetController 让\"停止\"变得有理有据！")
        return 0
    else:
        print("⚠️  验证部分通过：需要进一步优化")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
