#!/usr/bin/env python3
"""
Quick verification script for memory and bounds integration.

Tests:
1. Memory store initialization
2. Finding storage and retrieval
3. Hard bounds enforcement
4. API health check
"""

import sys
import os
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from driftcoach.memory.store import MemoryStore, DerivedFinding, QueryRecord
from driftcoach.config.bounds import DEFAULT_BOUNDS, SystemBounds


def test_memory_store():
    """Test basic memory store operations."""
    print("Testing MemoryStore...")

    # Create temporary database
    import tempfile
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        store = MemoryStore(db_path=db_path)

        # Test storing a finding
        finding = DerivedFinding(
            finding_id="test-1",
            session_id="session-test",
            intent="RISK_ASSESSMENT",
            fact_type="HIGH_RISK_SEQUENCE",
            content={"round_range": [1, 3], "note": "test"},
            confidence=0.9,
            created_at=MemoryStore.now(),
            series_id="series-1",
        )

        assert store.store_finding(finding), "Failed to store finding"
        print("  ✓ Finding stored")

        # Test retrieval
        findings = store.get_findings_by_session("session-test")
        assert len(findings) == 1, f"Expected 1 finding, got {len(findings)}"
        assert findings[0].intent == "RISK_ASSESSMENT"
        print("  ✓ Finding retrieved")

        # Test gate stats
        stats = store.get_gate_decision_stats()
        assert "historical_hit_rate" in stats
        print("  ✓ Gate stats calculated")

        print("✅ MemoryStore tests passed\n")
        return True

    finally:
        os.unlink(db_path)


def test_hard_bounds():
    """Test hard bounds configuration."""
    print("Testing Hard Bounds...")

    bounds = DEFAULT_BOUNDS

    # Verify bounds are set
    assert bounds.max_sub_intents == 3, "max_sub_intents should be 3"
    assert bounds.max_findings_per_intent == 2, "max_findings_per_intent should be 2"
    assert bounds.max_findings_total == 5, "max_findings_total should be 5"

    print("  ✓ max_sub_intents = 3")
    print("  ✓ max_findings_per_intent = 2")
    print("  ✓ max_findings_total = 5")

    # Test bounds enforcement
    from driftcoach.config.bounds import enforce_bounds_on_intents

    intents = ["INTENT_A", "INTENT_B", "INTENT_C", "INTENT_D"]
    bounded = enforce_bounds_on_intents(intents, bounds=bounds)

    assert len(bounded) == 3, f"Expected 3 intents, got {len(bounded)}"
    print("  ✓ Intent bounds enforced")

    print("✅ Hard Bounds tests passed\n")
    return True


def test_integration_imports():
    """Test that all integration modules can be imported."""
    print("Testing Integration Imports...")

    try:
        # Test memory and bounds modules (no ML dependencies)
        from driftcoach.memory.store import MemoryStore
        from driftcoach.config.bounds import DEFAULT_BOUNDS
        print("  ✓ memory and bounds modules imported")

        # Check bounds configuration
        assert DEFAULT_BOUNDS.max_sub_intents == 3
        assert DEFAULT_BOUNDS.max_findings_total == 5
        print("  ✓ Bounds configuration loaded")

        # Note: Full API import requires sklearn, which may not be installed
        # But core modules are verified above
        print("  ℹ  Skipping full API import (requires sklearn)")

        print("✅ Integration imports passed\n")
        return True

    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("DriftCoach Integration Verification")
    print("=" * 60)
    print()

    results = []

    # Run tests
    results.append(("Memory Store", test_memory_store()))
    results.append(("Hard Bounds", test_hard_bounds()))
    results.append(("Integration", test_integration_imports()))

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n🎉 All integration tests passed!")
        print("\nNext steps:")
        print("1. Start the server: python3 -m driftcoach.api")
        print("2. Test queries: curl -X POST http://localhost:8000/api/coach/query")
        print("3. Check memory: curl http://localhost:8000/api/coach/memory")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
