"""
Decision Mapper: Maps context state to coaching decision.

This is the critical layer that bridges the gap from 1→2:
- From: Context_State (technical state)
- To: Coaching_Decision (actionable insight)

Core philosophy:
- Never refuse to answer when ANY evidence exists
- Always provide a degraded decision with appropriate confidence
- Explicitly signal uncertainty level
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DecisionPath(Enum):
    """
    Three-way decision path (not binary).
    """
    STANDARD = "standard"       # Full evidence → normal conclusion
    DEGRADED = "degraded"       # Partial evidence → degraded conclusion
    REJECT = "reject"           # No evidence → explicit refusal


@dataclass
class UncertaintyMetrics:
    """
    Quantifies the uncertainty in the current context.
    """
    total: float                  # Total uncertainty score (0-1)
    missing_outcome: float = 0.0   # Missing outcome field impact
    small_sample: float = 0.0      # Small sample size impact
    no_comparison: float = 0.0      # No series comparison impact
    missing_facts: List[str] = None # List of what's missing

    def __post_init__(self):
        if self.missing_facts is None:
            self.missing_facts = []

    @property
    def severity(self) -> str:
        """Uncertainty severity level."""
        if self.total >= 0.8:
            return "CRITICAL"
        elif self.total >= 0.5:
            return "HIGH"
        elif self.total >= 0.3:
            return "MEDIUM"
        else:
            return "LOW"


@dataclass
class CoachingDecision:
    """
    Actionable coaching decision.

    This is the "y" in f(x)=y that coaches can actually use.
    """
    decision_path: DecisionPath
    claim: str                    # Main conclusion
    verdict: str                  # YES/NO/LOW_CONFIDENCE/INSUFFICIENT
    confidence: float             # 0-1
    support_facts: List[str]      # Supporting evidence
    counter_facts: List[str]      # Counter-evidence
    followups: List[str]          # Actionable next steps
    caveats: List[str]             # Explicit uncertainty warnings
    metadata: Dict[str, Any]       # Additional info


class DecisionMapper:
    """
    Maps context state to coaching decision.

    Core algorithm:
    1. Price the uncertainty (how bad is the missing data?)
    2. Choose decision path (STANDARD / DEGRADED / REJECT)
    3. Generate decision based on available evidence
    """

    def __init__(self):
        pass

    def map_to_decision(
        self,
        context: Dict[str, Any],
        intent: str,
        facts: Dict[str, List[Dict[str, Any]]],
        bounds: Any = None
    ) -> CoachingDecision:
        """
        Main mapping function.

        Args:
            context: Context metadata (outcome_field, series_pool, etc.)
            intent: Query intent
            facts: Available facts by type
            bounds: System bounds

        Returns:
            Coaching decision
        """
        # Step 1: Price the uncertainty
        uncertainty = self._price_uncertainty(context, facts)

        # Step 2: Choose decision path
        decision_path = self._choose_decision_path(uncertainty, facts)

        logger.info(
            f"[DECISION_MAPPER] intent={intent}, path={decision_path.value}, "
            f"uncertainty={uncertainty.total:.2f}, severity={uncertainty.severity}"
        )

        # Step 3: Generate decision
        if decision_path == DecisionPath.STANDARD:
            return self._generate_standard_decision(intent, facts, bounds)
        elif decision_path == DecisionPath.DEGRADED:
            return self._generate_degraded_decision(intent, facts, uncertainty, bounds)
        else:
            return self._generate_rejection(intent, facts, uncertainty)

    def _price_uncertainty(
        self,
        context: Dict[str, Any],
        facts: Dict[str, List[Dict[str, Any]]]
    ) -> UncertaintyMetrics:
        """
        Calculate the "price" of missing data.

        Each missing feature adds to the uncertainty score.
        """
        schema = context.get("schema", {}) or {}
        ev = context.get("evidence", {}) or {}

        # Missing outcome (high impact)
        outcome_field = schema.get("outcome_field") or schema.get("outcomeField", "UNKNOWN")
        missing_outcome = 0.4 if outcome_field == "NOT_FOUND" else 0.0

        # Small sample size (medium impact)
        states_count = ev.get("states_count", 0)
        small_sample = max(0, (20 - states_count) / 20 * 0.3) if states_count < 20 else 0.0

        # No comparison data (medium impact)
        series_pool = ev.get("seriesPool", ev.get("series_pool", 0))
        no_comparison = 0.2 if series_pool == 0 else 0.0

        # Missing fact types
        missing_facts = []
        total_facts = sum(len(f) for f in facts.values())

        if total_facts == 0:
            missing_facts.append("完全无可用数据")

        # Calculate total uncertainty
        total_uncertainty = missing_outcome + small_sample + no_comparison

        # Cap at 1.0
        total_uncertainty = min(1.0, total_uncertainty)

        return UncertaintyMetrics(
            total=total_uncertainty,
            missing_outcome=missing_outcome,
            small_sample=small_sample,
            no_comparison=no_comparison,
            missing_facts=missing_facts
        )

    def _choose_decision_path(
        self,
        uncertainty: UncertaintyMetrics,
        facts: Dict[str, List[Dict[str, Any]]]
    ) -> DecisionPath:
        """
        Choose decision path based on uncertainty and available evidence.

        Thresholds:
        - total >= 0.8 → REJECT (too uncertain)
        - total >= 0.4 → DEGRADED (uncertain but can provide value)
        - total < 0.4 → STANDARD (confident)
        """
        total_facts = sum(len(f) for f in facts.values())

        # No facts at all → reject
        if total_facts == 0:
            return DecisionPath.REJECT

        # High uncertainty → reject
        if uncertainty.total >= 0.8:
            return DecisionPath.REJECT

        # Medium uncertainty → degraded
        if uncertainty.total >= 0.4:
            return DecisionPath.DEGRADED

        # Low uncertainty → standard
        return DecisionPath.STANDARD

    def _generate_standard_decision(
        self,
        intent: str,
        facts: Dict[str, List[Dict[str, Any]]],
        bounds: Any
    ) -> CoachingDecision:
        """
        Generate standard decision with high confidence.

        Delegates to intent-specific handlers.
        """
        from driftcoach.analysis.synthesizer_router import AnswerSynthesizer

        synthesizer = AnswerSynthesizer()
        from driftcoach.analysis.answer_synthesizer import AnswerInput

        # Create dummy AnswerInput
        inp = AnswerInput(
            question=f"Analysis for {intent}",
            intent=intent,
            required_facts=[],
            facts=facts,
            series_id="unknown"
        )

        result = synthesizer.synthesize(inp, bounds)

        return CoachingDecision(
            decision_path=DecisionPath.STANDARD,
            claim=result.claim,
            verdict=result.verdict,
            confidence=result.confidence,
            support_facts=result.support_facts,
            counter_facts=result.counter_facts,
            followups=result.followups,
            caveats=[],  # No caveats for standard decisions
            metadata={"quality": "standard"}
        )

    def _generate_degraded_decision(
        self,
        intent: str,
        facts: Dict[str, List[Dict[str, Any]]],
        uncertainty: UncertaintyMetrics,
        bounds: Any
    ) -> CoachingDecision:
        """
        Generate degraded decision based on partial evidence.

        KEY: Never refuse to answer when ANY evidence exists.
        """
        # Extract available facts (any fact type)
        available_facts = []
        for fact_type, fact_list in facts.items():
            available_facts.extend(fact_list)

        if not available_facts:
            # Should not happen here (would be reject path)
            return self._generate_rejection(intent, facts, uncertainty)

        # Generate caveats based on uncertainty
        caveats = []

        if uncertainty.missing_outcome > 0:
            caveats.append("缺少胜负结果数据")

        if uncertainty.small_sample > 0:
            caveats.append(f"样本量较小（{uncertainty.severity}）")

        if uncertainty.no_comparison > 0:
            caveats.append("缺少对比数据")

        # Generate degraded claim
        fact_summary = self._summarize_facts(available_facts)

        claim = f"基于{len(available_facts)}条有限证据的初步分析：{fact_summary}"

        # Adjust confidence based on uncertainty
        base_confidence = 0.5
        degraded_confidence = base_confidence * (1.0 - uncertainty.total)
        degraded_confidence = max(0.25, min(0.45, degraded_confidence))

        return CoachingDecision(
            decision_path=DecisionPath.DEGRADED,
            claim=claim,
            verdict="LOW_CONFIDENCE",
            confidence=round(degraded_confidence, 2),
            support_facts=self._format_facts(available_facts[:3]),
            counter_facts=[],
            followups=self._generate_followups(available_facts, uncertainty),
            caveats=caveats,
            metadata={
                "quality": "degraded",
                "uncertainty_total": uncertainty.total,
                "uncertainty_severity": uncertainty.severity,
                "available_evidence_count": len(available_facts)
            }
        )

    def _generate_rejection(
        self,
        intent: str,
        facts: Dict[str, List[Dict[str, Any]]],
        uncertainty: UncertaintyMetrics
    ) -> CoachingDecision:
        """
        Generate explicit refusal when truly no evidence exists.

        This should be rare (only when total_facts == 0).
        """
        total_facts = sum(len(f) for f in facts.values())

        return CoachingDecision(
            decision_path=DecisionPath.REJECT,
            claim="当前完全无可用数据，无法进行分析",
            verdict="INSUFFICIENT",
            confidence=0.2,
            support_facts=[],
            counter_facts=[f"总证据数: {total_facts}"],
            followups=[
                "补充事件数据文件",
                "确认数据源可用",
                "尝试简化查询"
            ],
            caveats=["完全无证据"],
            metadata={
                "quality": "rejected",
                "reason": "no_evidence" if total_facts == 0 else "too_uncertain"
            }
        )

    def _summarize_facts(self, facts: List[Dict[str, Any]]) -> str:
        """Generate a brief summary of available facts."""
        if not facts:
            return "无可用数据"

        # Count fact types
        fact_types = {}
        for fact in facts:
            fact_type = fact.get("fact_type", "UNKNOWN")
            fact_types[fact_type] = fact_types.get(fact_type, 0) + 1

        # Generate summary
        if len(fact_types) == 1:
            type_name, count = list(fact_types.items())[0]
            return f"检测到 {count} 个 {type_name}"
        else:
            top_types = sorted(fact_types.items(), key=lambda x: -x[1])[:2]
            type_desc = "、".join([f"{count}个{t}" for t, count in top_types])
            return f"检测到 {type_desc}"

    def _format_facts(self, facts: List[Dict[str, Any]]) -> List[str]:
        """Format facts for display."""
        formatted = []

        for fact in facts[:3]:
            fact_type = fact.get("fact_type", "fact")
            note = fact.get("note", "")

            if note:
                formatted.append(f"{fact_type}: {note}")
            else:
                formatted.append(fact_type)

        return formatted

    def _generate_followups(
        self,
        facts: List[Dict[str, Any]],
        uncertainty: UncertaintyMetrics
    ) -> List[str]:
        """Generate actionable follow-up suggestions."""
        followups = []

        # Suggest based on what's missing
        if uncertainty.missing_outcome > 0:
            followups.append("补充胜负结果数据")

        if uncertainty.small_sample > 0.1:
            followups.append("增加样本量（更多局数/比赛）")

        if uncertainty.no_comparison > 0:
            followups.append("添加对比数据（其他比赛/选手）")

        # Suggest based on what's available
        fact_types = set(f.get("fact_type", "UNKNOWN") for f in facts)

        if "ROUND_SWING" in fact_types:
            followups.append("深入分析反转回合的战术决策")

        if "HIGH_RISK_SEQUENCE" in fact_types:
            followups.append("回顾高风险回合的经济管理")

        if "FORCE_BUY_ROUND" in fact_types:
            followups.append("评估强起时机和收益")

        return followups[:3]


def map_to_coaching_decision(
    context: Dict[str, Any],
    intent: str,
    facts: Dict[str, List[Dict[str, Any]]],
    bounds: Any = None
) -> CoachingDecision:
    """
    Public API: Map context to coaching decision.

    This is the main entry point for the decision mapping layer.
    """
    mapper = DecisionMapper()
    return mapper.map_to_decision(context, intent, facts, bounds)
