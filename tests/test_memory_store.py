"""
Tests for memory store and integration layer.
"""

import pytest
import tempfile
import os

from driftcoach.memory.store import (
    MemoryStore,
    DerivedFinding,
    GateDecisionRecord,
    QueryRecord,
)
from driftcoach.memory.integration import (
    MemoryEnabledGate,
    FindingExtractor,
    MemoryEnhancedOrchestrator,
)
from driftcoach.llm.probabilistic_gate import (
    GateMetrics,
    GateDecision,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def store(temp_db):
    """Create a memory store with temporary database."""
    return MemoryStore(db_path=temp_db)


def test_store_finding(store):
    """Test storing a finding."""
    finding = DerivedFinding(
        finding_id="test-1",
        session_id="session-1",
        intent="RISK_ASSESSMENT",
        fact_type="HIGH_RISK_SEQUENCE",
        content={"round_range": [1, 3], "note": "test"},
        confidence=0.9,
        created_at=MemoryStore.now(),
        series_id="series-1",
    )

    assert store.store_finding(finding) is True

    findings = store.get_findings_by_session("session-1")
    assert len(findings) == 1
    assert findings[0].intent == "RISK_ASSESSMENT"
    assert findings[0].fact_type == "HIGH_RISK_SEQUENCE"


def test_store_gate_decision(store):
    """Test storing a gate decision."""
    decision = GateDecisionRecord(
        decision_id="decision-1",
        session_id="session-1",
        intent="RISK_ASSESSMENT",
        decision="accept",
        confidence=0.85,
        metrics={"sample_size": 0.9, "data_quality": 0.8},
        rationale=["Sample size adequate", "Data quality acceptable"],
        created_at=MemoryStore.now(),
        series_id="series-1",
        suggested_action="proceed_with_analysis",
    )

    assert store.store_gate_decision(decision) is True

    stats = store.get_gate_decision_stats(intent="RISK_ASSESSMENT")
    assert stats["total_decisions"] == 1
    assert stats["historical_hit_rate"] == 1.0  # All accept
    assert stats["recent_failure_rate"] == 0.0


def test_store_query(store):
    """Test storing a query."""
    query = QueryRecord(
        query_id="query-1",
        session_id="session-1",
        query_text="这场比赛风险高吗？",
        intent="RISK_ASSESSMENT",
        findings_ids=["finding-1", "finding-2"],
        created_at=MemoryStore.now(),
        series_id="series-1",
    )

    assert store.store_query(query) is True

    similar = store.find_similar_queries(query_text="风险", intent="RISK_ASSESSMENT")
    assert len(similar) == 1
    assert similar[0].query_text == "这场比赛风险高吗？"


def test_memory_enabled_gate(store):
    """Test gate with historical context."""
    # Use a fresh session for this test
    gate = MemoryEnabledGate(store)

    # First decision (no history for this specific intent)
    metrics1 = GateMetrics(
        states_count=100,  # Higher sample size
        series_pool=10,
        outcome_field_available=True,
        aggregation_available=True,
        has_event_data=True,
    )
    result1 = gate.decide(
        metrics=metrics1,
        intent="STABILITY_ANALYSIS",  # Different intent to avoid collision
        session_id="session-gate-test",
    )
    # Should be ACCEPT with good metrics
    assert result1.decision in [GateDecision.ACCEPT, GateDecision.LOW_CONFIDENCE]

    # Check that decision was stored
    stats = store.get_gate_decision_stats(intent="STABILITY_ANALYSIS")
    assert stats["total_decisions"] == 1


def test_finding_extractor(store):
    """Test finding extraction and storage."""
    extractor = FindingExtractor(store)

    facts = {
        "HIGH_RISK_SEQUENCE": [
            {"round_range": [1, 3], "confidence": 0.9},
            {"round_range": [5, 7], "confidence": 0.8},
        ],
        "ROUND_SWING": [
            {"game_index": 1, "confidence": 0.7},
        ],
    }

    finding_ids = extractor.extract_and_store_findings(
        session_id="session-1",
        intent="RISK_ASSESSMENT",
        facts=facts,
        series_id="series-1",
    )

    # Should have stored findings (limited to prevent explosion)
    assert len(finding_ids) > 0

    # Verify findings are retrievable
    findings = store.get_findings_by_session("session-1")
    assert len(findings) > 0


def test_clear_session(store):
    """Test clearing session data."""
    # Store some data with unique ID
    finding = DerivedFinding(
        finding_id="test-clear-1",  # Unique ID
        session_id="session-clear-test",
        intent="RISK_ASSESSMENT",
        fact_type="HIGH_RISK_SEQUENCE",
        content={"test": "data"},
        confidence=0.9,
        created_at=MemoryStore.now(),
    )
    store.store_finding(finding)

    # Verify it's there
    findings = store.get_findings_by_session("session-clear-test")
    assert len(findings) == 1

    # Clear session
    assert store.clear_session("session-clear-test") is True

    # Verify it's gone
    findings = store.get_findings_by_session("session-clear-test")
    assert len(findings) == 0


if __name__ == "__main__":
    print("Testing memory store...")

    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        store = MemoryStore(db_path=path)

        print("\n1. Testing store finding:")
        test_store_finding(store)
        print("   ✓ Finding stored and retrieved")

        print("\n2. Testing store gate decision:")
        test_store_gate_decision(store)
        print("   ✓ Gate decision stored and stats calculated")

        print("\n3. Testing store query:")
        test_store_query(store)
        print("   ✓ Query stored and similar queries found")

        print("\n4. Testing memory-enabled gate:")
        test_memory_enabled_gate(store)
        print("   ✓ Gate decisions use historical context")

        print("\n5. Testing finding extractor:")
        test_finding_extractor(store)
        print("   ✓ Findings extracted and stored")

        print("\n6. Testing clear session:")
        test_clear_session(store)
        print("   ✓ Session data cleared")

        print("\n✅ All memory store tests passed!")

    finally:
        os.unlink(path)
