"""
Spec Implementation: 从 Intent 到 Spec 的映射

这是 DriftCoach L4 分治的核心：让不同 query 看到不同的 facts 子集
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


# =============================================================================
# 1. Spec Focus（规格焦点）
# =============================================================================

class SpecFocus(Enum):
    """Spec 关注的维度/子空间（6 个 MVP spec）"""
    ECON = "ECON"                    # 经济：强起/保枪/经济崩盘
    RISK = "RISK"                    # 风险：高风险序列/局势波动
    MAP = "MAP"                      # 地图：点位控制/薄弱点
    PLAYER = "PLAYER"                # 球员：选手表现/影响
    SUMMARY = "SUMMARY"              # 总结：全局回顾/总结
    MOMENTUM = "MOMENTUM"            # 动能：势能变化/阶段对比


# =============================================================================
# 2. Required Evidence（必需证据）
# =============================================================================

@dataclass
class RequiredEvidence:
    """最小充分证据类型 + 允许缺什么"""

    primary_fact_types: List[str]           # 必需的证据类型（至少需要一种）
    optional_fact_types: List[str] = field(default_factory=list)  # 可选的证据类型
    required_schema_fields: List[str] = field(default_factory=list)  # 必需的 schema 字段
    allowed_missing_fields: List[str] = field(default_factory=list)   # 允许缺失的字段


# =============================================================================
# 3. Spec Budget（硬上界）
# =============================================================================

@dataclass
class SpecBudget:
    """Per-spec 硬上界（防止爆炸）"""

    max_facts_total: int = 5                # 总 fact 数量
    max_facts_per_type: int = 3             # 每个 fact 类型数量
    max_events_window: Optional[int] = None # 最多看多少 events
    max_patches: int = 0                    # 是否允许补丁（0=不允许）
    max_analysis_methods: int = 2           # 最多运行多少种分析方法


# =============================================================================
# 4. Output Contract（输出契约）
# =============================================================================

@dataclass
class OutputContract:
    """输出形态：STANDARD/DEGRADED/REJECT 的触发条件"""

    standard_min_confidence: float = 0.7
    standard_min_facts: int = 2
    degraded_max_uncertainty: float = 0.8
    degraded_min_facts: int = 1
    required_fields: List[str] = field(default_factory=lambda: ["claim", "verdict", "confidence", "support_facts"])
    optional_fields: List[str] = field(default_factory=lambda: ["caveats", "followups", "counter_facts"])


# =============================================================================
# 5. Spec（完整定义）
# =============================================================================

@dataclass
class Spec:
    """
    Spec（规格）：定义"算什么、允许缺什么、上界是多少、输出形态是什么"

    核心作用：收缩可见性（search space reduction）
    """

    focus: SpecFocus
    required_evidence: RequiredEvidence
    budget: SpecBudget
    output_contract: OutputContract

    # 该 spec 支持的 intents（用于映射）
    intents: List[str] = field(default_factory=list)


# =============================================================================
# 6. 6 个 MVP Spec 实例
# =============================================================================

# Spec 1: ECON（经济分析）
ECON_SPEC = Spec(
    focus=SpecFocus.ECON,
    required_evidence=RequiredEvidence(
        primary_fact_types=[
            "FORCE_BUY_ROUND",         # 强起回合
            "ECO_COLLAPSE_SEQUENCE",   # 经济崩盘
            "ECONOMIC_PATTERN"         # 经济模式
        ],
        optional_fact_types=["FULL_BUY_ROUND", "ROUND_SWING"],
        required_schema_fields=[],
        allowed_missing_fields=["Series.winner", "teams.score", "result"]
    ),
    budget=SpecBudget(
        max_facts_total=5,
        max_facts_per_type=3,
        max_events_window=500,
        max_patches=0,
        max_analysis_methods=2
    ),
    output_contract=OutputContract(
        standard_min_confidence=0.75,
        standard_min_facts=2,
        degraded_max_uncertainty=0.7,
        degraded_min_facts=1
    ),
    intents=["ECONOMIC_COUNTERFACTUAL", "ECONOMIC_FAILURE", "TACTICAL_EVAL"]
)


# Spec 2: RISK（风险评估）
RISK_SPEC = Spec(
    focus=SpecFocus.RISK,
    required_evidence=RequiredEvidence(
        primary_fact_types=["HIGH_RISK_SEQUENCE", "ROUND_SWING"],
        optional_fact_types=["ECO_COLLAPSE_SEQUENCE", "OBJECTIVE_LOSS_CHAIN"],
        required_schema_fields=[],
        allowed_missing_fields=["Series.winner", "teams.score"]
    ),
    budget=SpecBudget(
        max_facts_total=5,
        max_facts_per_type=3,
        max_events_window=1000,
        max_patches=0,
        max_analysis_methods=2
    ),
    output_contract=OutputContract(
        standard_min_confidence=0.7,
        standard_min_facts=2,
        degraded_max_uncertainty=0.6,
        degraded_min_facts=1
    ),
    intents=["RISK_ASSESSMENT", "STABILITY_ANALYSIS", "COLLAPSE_ONSET_ANALYSIS"]
)


# Spec 3: MAP（地图分析）
MAP_SPEC = Spec(
    focus=SpecFocus.MAP,
    required_evidence=RequiredEvidence(
        primary_fact_types=["OBJECTIVE_LOSS_CHAIN", "HIGH_RISK_SEQUENCE"],
        optional_fact_types=["ROUND_SWING"],
        required_schema_fields=[],
        allowed_missing_fields=["Series.winner", "teams.score"]
    ),
    budget=SpecBudget(
        max_facts_total=4,
        max_facts_per_type=2,
        max_events_window=800,
        max_patches=0,
        max_analysis_methods=2
    ),
    output_contract=OutputContract(
        standard_min_confidence=0.7,
        standard_min_facts=2,
        degraded_max_uncertainty=0.7,
        degraded_min_facts=1
    ),
    intents=["MAP_WEAK_POINT", "EXECUTION_VS_STRATEGY"]
)


# Spec 4: PLAYER（球员分析）
PLAYER_SPEC = Spec(
    focus=SpecFocus.PLAYER,
    required_evidence=RequiredEvidence(
        primary_fact_types=["PLAYER_IMPACT_STAT", "ROUND_SWING"],
        optional_fact_types=["HIGH_RISK_SEQUENCE"],
        required_schema_fields=[],
        allowed_missing_fields=["Series.winner", "teams.score"]
    ),
    budget=SpecBudget(
        max_facts_total=4,
        max_facts_per_type=2,
        max_events_window=1000,
        max_patches=0,
        max_analysis_methods=2
    ),
    output_contract=OutputContract(
        standard_min_confidence=0.7,
        standard_min_facts=2,
        degraded_max_uncertainty=0.75,
        degraded_min_facts=1
    ),
    intents=["PLAYER_REVIEW", "COUNTERFACTUAL_PLAYER_IMPACT"]
)


# Spec 5: SUMMARY（总结分析）
SUMMARY_SPEC = Spec(
    focus=SpecFocus.SUMMARY,
    required_evidence=RequiredEvidence(
        primary_fact_types=["CONTEXT_ONLY"],
        optional_fact_types=["ROUND_SWING", "HIGH_RISK_SEQUENCE", "ECO_COLLAPSE_SEQUENCE"],
        required_schema_fields=[],
        allowed_missing_fields=["Series.winner", "teams.score", "result"]
    ),
    budget=SpecBudget(
        max_facts_total=3,
        max_facts_per_type=1,
        max_events_window=2000,
        max_patches=0,
        max_analysis_methods=1
    ),
    output_contract=OutputContract(
        standard_min_confidence=0.6,
        standard_min_facts=1,
        degraded_max_uncertainty=0.8,
        degraded_min_facts=1
    ),
    intents=["MATCH_SUMMARY", "MATCH_REVIEW"]
)


# Spec 6: MOMENTUM（动能分析）
MOMENTUM_SPEC = Spec(
    focus=SpecFocus.MOMENTUM,
    required_evidence=RequiredEvidence(
        primary_fact_types=["ROUND_SWING"],
        optional_fact_types=["HIGH_RISK_SEQUENCE"],
        required_schema_fields=[],
        allowed_missing_fields=["Series.winner", "teams.score"]
    ),
    budget=SpecBudget(
        max_facts_total=5,
        max_facts_per_type=3,
        max_events_window=1500,
        max_patches=0,
        max_analysis_methods=2
    ),
    output_contract=OutputContract(
        standard_min_confidence=0.7,
        standard_min_facts=2,
        degraded_max_uncertainty=0.7,
        degraded_min_facts=1
    ),
    intents=["MOMENTUM_ANALYSIS", "PHASE_COMPARISON"]
)


# =============================================================================
# 7. Intent → Spec 映射表
# =============================================================================

INTENT_TO_SPEC_MAP: Dict[str, Spec] = {
    # ECON spec
    "ECONOMIC_COUNTERFACTUAL": ECON_SPEC,
    "ECONOMIC_FAILURE": ECON_SPEC,
    "TACTICAL_EVAL": ECON_SPEC,

    # RISK spec
    "RISK_ASSESSMENT": RISK_SPEC,
    "STABILITY_ANALYSIS": RISK_SPEC,
    "COLLAPSE_ONSET_ANALYSIS": RISK_SPEC,

    # MAP spec
    "MAP_WEAK_POINT": MAP_SPEC,
    "EXECUTION_VS_STRATEGY": MAP_SPEC,

    # PLAYER spec
    "PLAYER_REVIEW": PLAYER_SPEC,
    "COUNTERFACTUAL_PLAYER_IMPACT": PLAYER_SPEC,

    # SUMMARY spec
    "MATCH_SUMMARY": SUMMARY_SPEC,
    "MATCH_REVIEW": SUMMARY_SPEC,

    # MOMENTUM spec
    "MOMENTUM_ANALYSIS": MOMENTUM_SPEC,
    "PHASE_COMPARISON": MOMENTUM_SPEC,
}


# =============================================================================
# 8. Spec Recognizer（Spec 识别器）
# =============================================================================

class SpecRecognizer:
    """
    Spec 识别器：从 query 和 intent 推导出 spec

    核心作用：让不同 query 看到不同的 facts 子集
    """

    @staticmethod
    def recognize_spec(intent: str, query: str = "") -> Spec:
        """
        从 intent 推导出 spec

        Args:
            intent: 意图类型（如 "RISK_ASSESSMENT"）
            query: 原始查询文本（可选，用于未来增强）

        Returns:
            Spec 实例
        """
        # 查表
        spec = INTENT_TO_SPEC_MAP.get(intent)

        if spec is None:
            # 默认回退到 SUMMARY_SPEC（最宽松）
            spec = SUMMARY_SPEC

        return spec

    @staticmethod
    def get_allowed_fact_types(intent: str) -> List[str]:
        """
        获取 intent 允许的 fact types

        这是 spec 收缩可见性的关键实现
        """
        spec = SpecRecognizer.recognize_spec(intent)

        # 返回允许的 fact types
        allowed = (
            spec.required_evidence.primary_fact_types +
            spec.required_evidence.optional_fact_types
        )

        return allowed

    @staticmethod
    def filter_facts_by_spec(intent: str, all_facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        只保留 spec 允许的 facts

        Args:
            intent: 意图类型
            all_facts: 所有挖掘到的 facts

        Returns:
            过滤后的 facts（只包含 spec 允许的类型）
        """
        allowed_types = SpecRecognizer.get_allowed_fact_types(intent)

        # 过滤 facts
        filtered = [
            f for f in all_facts
            if f.get("fact_type") in allowed_types
        ]

        # 应用 per-spec budget
        spec = SpecRecognizer.recognize_spec(intent)
        filtered = filtered[:spec.budget.max_facts_total]

        return filtered


# =============================================================================
# 9. 使用示例
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Spec Implementation Demo")
    print("=" * 70)
    print()

    # 示例 1: 从 intent 识别 spec
    print("示例 1: 从 intent 识别 spec")
    print("-" * 70)

    intent = "RISK_ASSESSMENT"
    spec = SpecRecognizer.recognize_spec(intent)

    print(f"Intent: {intent}")
    print(f"Spec Focus: {spec.focus.value}")
    print(f"Allowed Fact Types: {spec.required_evidence.primary_fact_types}")
    print(f"Max Facts Total: {spec.budget.max_facts_total}")
    print()

    # 示例 2: Spec 收缩可见性
    print("示例 2: Spec 收缩可见性")
    print("-" * 70)

    all_facts = [
        {"fact_type": "HIGH_RISK_SEQUENCE", "round": 5},
        {"fact_type": "ROUND_SWING", "round": 10},
        {"fact_type": "FORCE_BUY_ROUND", "round": 3},
        {"fact_type": "PLAYER_IMPACT_STAT", "player": "X"},
        {"fact_type": "ECO_COLLAPSE_SEQUENCE", "round": 15},
    ]

    print(f"所有 facts ({len(all_facts)}): {[f['fact_type'] for f in all_facts]}")

    risk_facts = SpecRecognizer.filter_facts_by_spec("RISK_ASSESSMENT", all_facts)
    econ_facts = SpecRecognizer.filter_facts_by_spec("ECONOMIC_COUNTERFACTUAL", all_facts)

    print(f"RISK spec 看到的 facts ({len(risk_facts)}): {[f['fact_type'] for f in risk_facts]}")
    print(f"ECON spec 看到的 facts ({len(econ_facts)}): {[f['fact_type'] for f in econ_facts]}")
    print()

    # 示例 3: 所有 6 个 MVP spec
    print("示例 3: 6 个 MVP Spec 总览")
    print("-" * 70)

    specs = [
        ("ECON", ECON_SPEC),
        ("RISK", RISK_SPEC),
        ("MAP", MAP_SPEC),
        ("PLAYER", PLAYER_SPEC),
        ("SUMMARY", SUMMARY_SPEC),
        ("MOMENTUM", MOMENTUM_SPEC),
    ]

    for name, spec in specs:
        print(f"\n{name}_SPEC:")
        print(f"  Intents: {', '.join(spec.intents)}")
        print(f"  Primary Facts: {', '.join(spec.required_evidence.primary_fact_types)}")
        print(f"  Max Facts: {spec.budget.max_facts_total}")
        print(f"  Output Confidence: {spec.output_contract.standard_min_confidence}")

    print()
    print("=" * 70)
    print("✅ Spec Implementation Complete!")
    print("=" * 70)
