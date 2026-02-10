"""
Divide and Conquer: Intent-based answer synthesis.

Each intent is handled by an independent handler, making the system:
- Testable: Each handler can be tested independently
- Evolvable: New intents can be added without modifying existing code
- Bounded: Each handler respects the global bounds
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from driftcoach.config.bounds import SystemBounds, DEFAULT_BOUNDS
from driftcoach.analysis.answer_synthesizer import (
    AnswerInput,
    AnswerSynthesisResult,
    _support_strings,
    _counter_strings,
    _limit_followups,
)


@dataclass
class HandlerContext:
    """
    Context passed to each handler.
    Contains the input and system bounds.
    """
    input: AnswerInput
    bounds: SystemBounds
    intent: str

    @property
    def facts(self) -> Dict[str, List[Dict[str, Any]]]:
        return self.input.facts or {}

    def get_facts(self, fact_type: str) -> List[Dict[str, Any]]:
        """Get facts of a specific type."""
        return self.facts.get(fact_type, [])

    def has_facts(self, fact_type: str, min_count: int = 1) -> bool:
        """Check if there are enough facts of a type."""
        return len(self.get_facts(fact_type)) >= min_count


class IntentHandler(ABC):
    """
    Base class for intent-specific answer handlers.

    Each handler:
    1. Declares which intents it can handle
    2. Implements the synthesis logic for those intents
    3. Respects the global bounds
    """

    @abstractmethod
    def can_handle(self, intent: str) -> bool:
        """
        Check if this handler can process the given intent.

        Args:
            intent: The intent string (e.g., "RISK_ASSESSMENT")

        Returns:
            True if this handler can process the intent
        """
        pass

    @abstractmethod
    def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
        """
        Process the intent and generate an answer.

        Args:
            ctx: Handler context with input and bounds

        Returns:
            Answer synthesis result
        """
        pass

    def get_support_facts(
        self,
        ctx: HandlerContext,
        fact_types: List[str],
        limit: Optional[int] = None
    ) -> List[str]:
        """Extract support facts from specified types."""
        all_facts = []
        for ft in fact_types:
            all_facts.extend(ctx.get_facts(ft))

        return _support_strings(
            all_facts,
            limit=limit or ctx.bounds.max_support_facts,
            bounds=ctx.bounds
        )

    def get_counter_facts(
        self,
        ctx: HandlerContext,
        fact_types: List[str],
        limit: Optional[int] = None
    ) -> List[str]:
        """Extract counter facts from specified types."""
        all_facts = []
        for ft in fact_types:
            all_facts.extend(ctx.get_facts(ft))

        return _counter_strings(
            all_facts,
            limit=limit or ctx.bounds.max_counter_facts,
            bounds=ctx.bounds
        )


class RiskAssessmentHandler(IntentHandler):
    """
    Handler for risk assessment queries.
    Intent: "RISK_ASSESSMENT"
    """

    def can_handle(self, intent: str) -> bool:
        return intent == "RISK_ASSESSMENT"

    def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
        # ✅ Phase 2: Spec 收缩可见性
        # 只使用 RISK_SPEC 允许的 facts
        from driftcoach.specs.spec_schema import SpecRecognizer, RISK_SPEC

        # ✅ L5: BudgetController - CLRS Chapter 5 rational stopping
        from driftcoach.analysis.budget_controller import (
            BudgetController,
            BudgetState,
            ConfidenceTarget,
            create_initial_state,
            create_default_target,
        )

        # 获取所有 facts（按类型分组）
        all_facts_by_type = {}
        for fact_type in RISK_SPEC.required_evidence.primary_fact_types:
            all_facts_by_type[fact_type] = ctx.get_facts(fact_type)

        # 应用 spec budget
        max_facts = RISK_SPEC.budget.max_facts_per_type

        # 创建 fact 候选列表（按优先级排序）
        # 优先级：HIGH_RISK_SEQUENCE > ROUND_SWING > ECO_COLLAPSE_SEQUENCE
        fact_candidates = []
        fact_candidates.extend([
            ("HIGH_RISK_SEQUENCE", f)
            for f in all_facts_by_type.get("HIGH_RISK_SEQUENCE", [])[:max_facts]
        ])
        fact_candidates.extend([
            ("ROUND_SWING", f)
            for f in all_facts_by_type.get("ROUND_SWING", [])[:max_facts]
        ])
        fact_candidates.extend([
            ("ECO_COLLAPSE_SEQUENCE", f)
            for f in all_facts_by_type.get("ECO_COLLAPSE_SEQUENCE", [])[:max_facts]
        ])

        # 初始化 BudgetController
        controller = BudgetController()
        budget = ctx.bounds.max_facts_total  # 从 L3 bounds 获取预算
        state = create_initial_state(initial_confidence=0.0, budget=budget)
        target = create_default_target(target_confidence=0.7)

        # 已挖掘的 facts（按类型分组）
        mined_hrs = []
        mined_swings = []
        mined_eco = []

        # ✅ L5 核心循环：逐步挖掘，理性停止
        for fact_type, fact in fact_candidates:
            # 检查是否应该继续
            if not controller.should_continue(state, target):
                break

            # "挖掘"这个 fact（添加到已挖掘列表）
            if fact_type == "HIGH_RISK_SEQUENCE":
                mined_hrs.append(fact)
            elif fact_type == "ROUND_SWING":
                mined_swings.append(fact)
            elif fact_type == "ECO_COLLAPSE_SEQUENCE":
                mined_eco.append(fact)

            # 更新状态
            state.facts_mined += 1
            state.remaining_budget -= 1

            # 计算新的 confidence（基于当前已挖掘的 facts）
            new_confidence = self._calculate_confidence(mined_hrs, mined_swings)
            state.update_confidence(new_confidence)

        # 循环结束 → 使用已挖掘的 facts 生成决策
        # 优先级判断
        if len(mined_hrs) >= 2:
            return AnswerSynthesisResult(
                claim="这是一场高风险对局",
                verdict="YES",
                confidence=0.9,
                support_facts=self._format_facts(mined_hrs[:3]),
                counter_facts=[],
                followups=[]
            )

        elif len(mined_swings) >= 5:
            return AnswerSynthesisResult(
                claim="这是一场高风险对局",
                verdict="YES",
                confidence=0.75,
                support_facts=self._format_facts(mined_swings[:3]),
                counter_facts=[],
                followups=[]
            )

        else:
            # KEY: Always provide a degraded answer if ANY evidence exists
            # Use DecisionMapper to generate degraded decision
            from driftcoach.analysis.decision_mapper import DecisionMapper, DecisionPath

            available_facts = mined_hrs + mined_swings

            if available_facts:
                # Create minimal context for decision mapper
                context = {
                    "schema": {"outcome_field": "NOT_FOUND"},  # Assume missing
                    "evidence": {
                        "states_count": len(available_facts),
                        "seriesPool": 0
                    }
                }

                mapper = DecisionMapper()
                decision = mapper.map_to_decision(
                    context=context,
                    intent=ctx.intent,
                    facts={"HIGH_RISK_SEQUENCE": mined_hrs, "ROUND_SWING": mined_swings},
                    bounds=ctx.bounds
                )

                # Convert CoachingDecision to AnswerSynthesisResult
                return AnswerSynthesisResult(
                    claim=decision.claim,
                    verdict=decision.verdict,
                    confidence=decision.confidence,
                    support_facts=decision.support_facts,
                    counter_facts=decision.counter_facts,
                    followups=decision.followups
                )
            else:
                # Truly no evidence → explicit rejection
                return AnswerSynthesisResult(
                    claim="当前数据不足以评估风险水平（完全无可用证据）",
                    verdict="INSUFFICIENT",
                    confidence=0.3,
                    support_facts=[],
                    counter_facts=[
                        f"HIGH_RISK_SEQUENCE={len(mined_hrs)}",
                        f"ROUND_SWING={len(mined_swings)}"
                    ],
                    followups=["补充更多局数的风险片段", "核查关键局的输分原因"]
                )

    def _calculate_confidence(self, hrs: list, swings: list) -> float:
        """
        Calculate confidence based on mined facts.

        This is a simplified heuristic for L5-MVP.
        In production, this could use a more sophisticated model.

        Args:
            hrs: Mined HIGH_RISK_SEQUENCE facts
            swings: Mined ROUND_SWING facts

        Returns:
            Estimated confidence (0.0 to 1.0)
        """
        # Start with base confidence
        confidence = 0.0

        # HIGH_RISK_SEQUENCE contributes strongly
        if len(hrs) >= 2:
            confidence = max(confidence, 0.9)
        elif len(hrs) >= 1:
            confidence = max(confidence, 0.6)

        # ROUND_SWING contributes moderately
        if len(swings) >= 5:
            confidence = max(confidence, 0.75)
        elif len(swings) >= 3:
            confidence = max(confidence, 0.55)
        elif len(swings) >= 1:
            confidence = max(confidence, 0.35)

        return confidence

    def _format_facts(self, facts: list) -> List[str]:
        """
        Format facts into support strings.

        Args:
            facts: List of fact dictionaries

        Returns:
            List of formatted fact strings
        """
        if not facts:
            return []

        result = []
        for fact in facts[:3]:  # Limit to 3 facts
            note = fact.get("note", "")
            rr = fact.get("round_range", [])
            rr_str = f"R{rr[0]}-R{rr[1]}" if len(rr) == 2 else ""
            r = fact.get("round", "")
            r_str = f"R{r}" if r else ""
            pieces = [p for p in [r_str, rr_str, note] if p]
            result.append(" | ".join(pieces) if pieces else fact.get("fact_type", "fact"))

        return result


class EconomicCounterfactualHandler(IntentHandler):
    """
    Handler for economic counterfactual queries.
    Intent: "ECONOMIC_COUNTERFACTUAL"
    """

    def can_handle(self, intent: str) -> bool:
        return intent == "ECONOMIC_COUNTERFACTUAL"

    def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
        force_buy = ctx.get_facts("FORCE_BUY_ROUND")
        eco_collapse = ctx.get_facts("ECO_COLLAPSE_SEQUENCE")
        full_buy = ctx.get_facts("FULL_BUY_ROUND")

        if len(force_buy) > 0 and len(eco_collapse) > 0:
            return AnswerSynthesisResult(
                claim="强起决策很可能放大了风险，保枪可能更优",
                verdict="YES",
                confidence=0.82,
                support_facts=(
                    self.get_support_facts(ctx, ["FORCE_BUY_ROUND"], limit=1) +
                    self.get_support_facts(ctx, ["ECO_COLLAPSE_SEQUENCE"], limit=1)
                ),
                counter_facts=[],
                followups=[]
            )

        elif len(full_buy) > len(force_buy):
            return AnswerSynthesisResult(
                claim="即使保枪，结果也未必会更好",
                verdict="NO",
                confidence=0.55,
                support_facts=self.get_support_facts(ctx, ["FULL_BUY_ROUND"]),
                counter_facts=self.get_support_facts(ctx, ["FORCE_BUY_ROUND"]),
                followups=[]
            )

        else:
            # Try degraded decision with any available economic facts
            available_facts = force_buy + eco_collapse + full_buy

            if available_facts:
                # Use DecisionMapper for degraded decision
                from driftcoach.analysis.decision_mapper import DecisionMapper

                context = {
                    "schema": {"outcome_field": "NOT_FOUND"},
                    "evidence": {
                        "states_count": len(available_facts),
                        "seriesPool": 0
                    }
                }

                mapper = DecisionMapper()
                decision = mapper.map_to_decision(
                    context=context,
                    intent=ctx.intent,
                    facts={
                        "FORCE_BUY_ROUND": force_buy,
                        "ECO_COLLAPSE_SEQUENCE": eco_collapse,
                        "FULL_BUY_ROUND": full_buy
                    },
                    bounds=ctx.bounds
                )

                return AnswerSynthesisResult(
                    claim=decision.claim,
                    verdict=decision.verdict,
                    confidence=decision.confidence,
                    support_facts=decision.support_facts,
                    counter_facts=decision.counter_facts,
                    followups=decision.followups
                )
            else:
                # No economic data at all
                return AnswerSynthesisResult(
                    claim="缺少经济事件数据，无法判断强起/保枪效果",
                    verdict="INSUFFICIENT",
                    confidence=0.3,
                    support_facts=[],
                    counter_facts=[
                        f"FORCE_BUY_ROUND={len(force_buy)}",
                        f"ECO_COLLAPSE_SEQUENCE={len(eco_collapse)}",
                        f"FULL_BUY_ROUND={len(full_buy)}"
                    ],
                    followups=["补充关键强起回合的经济明细", "核查失分与强起回合的对应关系"]
                )


class MomentumAnalysisHandler(IntentHandler):
    """
    Handler for momentum analysis queries.
    Intents: "MOMENTUM_ANALYSIS", "MOMENTUM_SHIFT"
    """

    def can_handle(self, intent: str) -> bool:
        return intent in {"MOMENTUM_ANALYSIS", "MOMENTUM_SHIFT"}

    def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
        swings = ctx.get_facts("ROUND_SWING")

        if len(swings) > 0:
            return AnswerSynthesisResult(
                claim="比赛中出现过关键的局势反转",
                verdict="YES",
                confidence=0.78,
                support_facts=self.get_support_facts(ctx, ["ROUND_SWING"]),
                counter_facts=[],
                followups=[]
            )
        else:
            return AnswerSynthesisResult(
                claim="未发现能改变局势的反转",
                verdict="NO",
                confidence=0.45,
                support_facts=[],
                counter_facts=["ROUND_SWING=0"],
                followups=["检查关键局的开局/收官表现"]
            )


class StabilityAnalysisHandler(IntentHandler):
    """
    Handler for stability analysis queries.
    Intents: "STABILITY_ANALYSIS", "STABILITY_CHECK"
    """

    def can_handle(self, intent: str) -> bool:
        return intent in {"STABILITY_ANALYSIS", "STABILITY_CHECK"}

    def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
        from driftcoach.analysis.answer_synthesizer import _swings_across_segments

        swings = ctx.get_facts("ROUND_SWING")
        repeated = len(swings) >= 3 and _swings_across_segments(swings)

        if repeated:
            return AnswerSynthesisResult(
                claim="局势反转在多局段反复出现",
                verdict="YES",
                confidence=0.76,
                support_facts=self.get_support_facts(ctx, ["ROUND_SWING"]),
                counter_facts=[],
                followups=[]
            )
        else:
            return AnswerSynthesisResult(
                claim="局势反转更像偶发事件",
                verdict="NO",
                confidence=0.52 if swings else 0.4,
                support_facts=self.get_support_facts(ctx, ["ROUND_SWING"]),
                counter_facts=(
                    ["未提炼到 ROUND_SWING"] if not swings
                    else ["集中于单一局段，缺少跨局分布"]
                ),
                followups=["补充其他地图/局段的 swing 事件"]
            )


class CollapseOnsetHandler(IntentHandler):
    """
    Handler for collapse onset analysis.
    Intent: "COLLAPSE_ONSET_ANALYSIS"
    """

    def can_handle(self, intent: str) -> bool:
        return intent == "COLLAPSE_ONSET_ANALYSIS"

    def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
        eco = ctx.get_facts("ECO_COLLAPSE_SEQUENCE")
        swings = ctx.get_facts("ROUND_SWING")

        if eco:
            return AnswerSynthesisResult(
                claim="出现过经济崩盘/断档的起点，需要控制经济节奏",
                verdict="YES",
                confidence=0.78,
                support_facts=self.get_support_facts(ctx, ["ECO_COLLAPSE_SEQUENCE"]),
                counter_facts=self.get_support_facts(ctx, ["ROUND_SWING"]),
                followups=[]
            )

        elif swings:
            return AnswerSynthesisResult(
                claim="有局势波动，但尚不足以定位经济崩盘起点",
                verdict="INSUFFICIENT",
                confidence=0.45,
                support_facts=self.get_support_facts(ctx, ["ROUND_SWING"]),
                counter_facts=[],
                followups=["补充经济明细（loadout/money）以定位崩盘回合"]
            )

        else:
            return AnswerSynthesisResult(
                claim="缺少经济崩盘相关事件",
                verdict="INSUFFICIENT",
                confidence=0.3,
                support_facts=[],
                counter_facts=[
                    "ECO_COLLAPSE_SEQUENCE=0",
                    "ROUND_SWING=0"
                ],
                followups=["补充经济事件文件", "核查关键输分后的经济状态"]
            )


# TODO: Add remaining handlers
# - PhaseComparisonHandler
# - TacticalDecisionHandler
# - ExecutionStrategyHandler
# - MapWeakPointHandler
# - RoundBreakdownHandler


class FallbackHandler(IntentHandler):
    """
    Fallback handler for unrecognized intents.
    Attempts to provide a degraded answer based on any available facts.
    """

    def can_handle(self, intent: str) -> bool:
        return True  # Can handle any intent (fallback)

    def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
        # Try to extract any available facts
        all_facts = []
        for fact_type, facts in ctx.facts.items():
            all_facts.extend(facts)

        if all_facts:
            # Degraded decision
            return AnswerSynthesisResult(
                claim=f"基于有限数据的初步分析（{len(all_facts)}条证据）",
                verdict="LOW_CONFIDENCE",
                confidence=0.35,
                support_facts=self.get_support_facts(
                    ctx,
                    list(ctx.facts.keys())[:3]
                ),
                counter_facts=[
                    "缺少对应规则",
                    "数据不完整"
                ],
                followups=["补充意图映射或规则"]
            )
        else:
            return AnswerSynthesisResult(
                claim="缺少对应规则，无法生成结论",
                verdict="INSUFFICIENT",
                confidence=0.2,
                support_facts=[],
                counter_facts=[],
                followups=["补充意图映射或规则"]
            )
