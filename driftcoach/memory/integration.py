"""
Integration layer for memory store with existing DriftCoach components.

This module connects the memory layer to:
1. Probabilistic gate (for historical hit rates)
2. Answer synthesizer (for storing findings)
3. Query orchestrator (for storing query→findings mappings)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from driftcoach.memory.store import (
    MemoryStore,
    DerivedFinding,
    GateDecisionRecord,
    QueryRecord,
    gate_result_to_record,
)
from driftcoach.llm.probabilistic_gate import (
    GateMetrics,
    GateResult,
    probabilistic_evidence_gate,
)


class MemoryEnabledGate:
    """
    Evidence gate with memory integration.

    Uses historical decision data to improve gate accuracy.
    """

    def __init__(self, store: MemoryStore):
        """
        Initialize memory-enabled gate.

        Args:
            store: MemoryStore instance for historical data
        """
        self.store = store

    def decide(
        self,
        metrics: GateMetrics,
        intent: Optional[str] = None,
        strictness: float = 0.5,
        session_id: Optional[str] = None,
        series_id: Optional[str] = None,
    ) -> GateResult:
        """
        Make gate decision with historical context.

        Enriches metrics with historical hit rates before deciding.
        """
        # Get historical statistics for this intent
        stats = self.store.get_gate_decision_stats(intent=intent)
        historical_hit_rate = stats.get("historical_hit_rate", 0.5)
        recent_failure_rate = stats.get("recent_failure_rate", 0.0)

        # Enrich metrics with historical data
        metrics.historical_hit_rate = historical_hit_rate
        metrics.recent_failure_rate = recent_failure_rate

        # Make probabilistic decision
        result = probabilistic_evidence_gate(metrics, intent=intent, strictness=strictness)

        # Store decision for future learning
        if session_id:
            decision_record = gate_result_to_record(
                result,
                session_id=session_id,
                intent=intent or "unknown",
                series_id=series_id,
            )
            self.store.store_gate_decision(decision_record)

        return result


class FindingExtractor:
    """
    Extract and store findings from analysis results.

    Bridges the gap between analysis output and memory storage.
    """

    def __init__(self, store: MemoryStore):
        """
        Initialize finding extractor.

        Args:
            store: MemoryStore instance
        """
        self.store = store

    def extract_and_store_findings(
        self,
        session_id: str,
        intent: str,
        facts: Dict[str, List[Dict[str, Any]]],
        series_id: Optional[str] = None,
        player_id: Optional[str] = None,
    ) -> List[str]:
        """
        Extract findings from facts and store them.

        Args:
            session_id: Session identifier
            intent: Intent type
            facts: Facts dictionary from analysis
            series_id: Optional series ID
            player_id: Optional player ID

        Returns:
            List of finding IDs
        """
        finding_ids = []

        for fact_type, fact_list in facts.items():
            if not fact_list:
                continue

            # Store each fact as a finding
            for fact in fact_list[:2]:  # Limit to prevent explosion
                finding = DerivedFinding(
                    finding_id=MemoryStore.generate_id(),
                    session_id=session_id,
                    intent=intent,
                    fact_type=fact_type,
                    content=fact,
                    confidence=fact.get("confidence", 0.7),
                    created_at=MemoryStore.now(),
                    series_id=series_id,
                    player_id=player_id,
                    metadata={
                        "source": "analysis",
                    },
                )

                if self.store.store_finding(finding):
                    finding_ids.append(finding.finding_id)

        return finding_ids

    def store_synthesis_result(
        self,
        session_id: str,
        query_text: str,
        intent: str,
        synthesis_result: Any,
        findings_ids: List[str],
        gate_decision_id: Optional[str] = None,
        series_id: Optional[str] = None,
        player_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Store query and its synthesis result.

        Args:
            session_id: Session identifier
            query_text: Original query
            intent: Detected intent
            synthesis_result: AnswerSynthesisResult
            findings_ids: Associated finding IDs
            gate_decision_id: Optional gate decision ID
            series_id: Optional series ID
            player_id: Optional player ID

        Returns:
            Query ID if stored successfully, None otherwise
        """
        # Extract key info from synthesis result
        metadata = {
            "claim": synthesis_result.claim,
            "verdict": synthesis_result.verdict,
            "confidence": synthesis_result.confidence,
            "support_count": len(synthesis_result.support_facts),
            "counter_count": len(synthesis_result.counter_facts),
        }

        query = QueryRecord(
            query_id=MemoryStore.generate_id(),
            session_id=session_id,
            query_text=query_text,
            intent=intent,
            findings_ids=findings_ids,
            gate_decision_id=gate_decision_id,
            created_at=MemoryStore.now(),
            series_id=series_id,
            player_id=player_id,
        )

        if self.store.store_query(query):
            return query.query_id

        return None


class MemoryEnhancedOrchestrator:
    """
    Orchestrator with memory integration.

    Combines gate decisions, finding extraction, and query storage.
    """

    def __init__(self, store: Optional[MemoryStore] = None):
        """
        Initialize memory-enhanced orchestrator.

        Args:
            store: MemoryStore instance (creates new one if None)
        """
        self.store = store or MemoryStore()
        self.gate = MemoryEnabledGate(self.store)
        self.extractor = FindingExtractor(self.store)

    def orchestrate_query(
        self,
        session_id: str,
        query_text: str,
        intent: str,
        metrics: GateMetrics,
        facts: Dict[str, List[Dict[str, Any]]],
        synthesis_result: Any,
        series_id: Optional[str] = None,
        player_id: Optional[str] = None,
        strictness: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Full orchestration of a query with memory integration.

        Args:
            session_id: Session identifier
            query_text: Original query
            intent: Detected intent
            metrics: Gate metrics
            facts: Analysis facts
            synthesis_result: AnswerSynthesisResult
            series_id: Optional series ID
            player_id: Optional player ID
            strictness: Gate strictness

        Returns:
            Dictionary with gate decision, finding IDs, query ID
        """
        # 1. Make gate decision (with historical context)
        gate_result = self.gate.decide(
            metrics=metrics,
            intent=intent,
            strictness=strictness,
            session_id=session_id,
            series_id=series_id,
        )

        # 2. Extract and store findings
        findings_ids = []
        if gate_result.decision.value in ["accept", "low_confidence"]:
            findings_ids = self.extractor.extract_and_store_findings(
                session_id=session_id,
                intent=intent,
                facts=facts,
                series_id=series_id,
                player_id=player_id,
            )

        # 3. Store query record
        gate_decision_id = gate_result.rationale[0] if gate_result.rationale else None
        query_id = self.extractor.store_synthesis_result(
            session_id=session_id,
            query_text=query_text,
            intent=intent,
            synthesis_result=synthesis_result,
            findings_ids=findings_ids,
            gate_decision_id=gate_decision_id,
            series_id=series_id,
            player_id=player_id,
        )

        return {
            "gate_decision": gate_result,
            "findings_ids": findings_ids,
            "query_id": query_id,
            "session_id": session_id,
        }
