"""
Memory persistence layer for DriftCoach.

Stores:
1. DerivedFindings - Analysis results from queries
2. Gate decisions - Evidence gate outcomes
3. Query → Findings mappings - For retrieval and learning

Uses SQLite (can be migrated to Redis later).
"""

from __future__ import annotations

import sqlite3
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

from driftcoach.llm.probabilistic_gate import GateDecision, GateResult


@dataclass
class DerivedFinding:
    """A single analysis finding derived from data."""
    finding_id: str  # Unique identifier
    session_id: str  # Session this belongs to
    intent: str  # Intent type (e.g., "RISK_ASSESSMENT")
    fact_type: str  # Type of fact (e.g., "HIGH_RISK_SEQUENCE")
    content: Dict[str, Any]  # Finding content (JSON-serializable)
    confidence: float  # Confidence score (0-1)
    created_at: str  # ISO timestamp
    series_id: Optional[str] = None  # Associated series
    player_id: Optional[str] = None  # Associated player
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata


@dataclass
class GateDecisionRecord:
    """Record of an evidence gate decision."""
    decision_id: str  # Unique identifier
    session_id: str  # Session this belongs to
    intent: str  # Intent type
    decision: str  # Decision: "accept", "low_confidence", "reject"
    confidence: float  # Gate confidence (0-1)
    metrics: Dict[str, Any]  # Input metrics (sample_size, variance, etc.)
    rationale: List[str]  # Human-readable reasons
    created_at: str  # ISO timestamp
    series_id: Optional[str] = None
    suggested_action: Optional[str] = None


@dataclass
class QueryRecord:
    """Record of a query and its associated findings."""
    query_id: str  # Unique identifier
    session_id: str  # Session this belongs to
    query_text: str  # Original natural language query
    intent: str  # Detected intent
    findings_ids: List[str]  # Associated finding IDs
    created_at: str  # ISO timestamp
    gate_decision_id: Optional[str] = None  # Associated gate decision
    series_id: Optional[str] = None
    player_id: Optional[str] = None


class MemoryStore:
    """
    SQLite-based memory store for DriftCoach.

    Provides persistence for findings, gate decisions, and queries.
    Enables learning from historical performance.
    """

    def __init__(self, db_path: str = "driftcoach_memory.db"):
        """
        Initialize memory store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create findings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                finding_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                intent TEXT NOT NULL,
                fact_type TEXT NOT NULL,
                content JSON NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL,
                series_id TEXT,
                player_id TEXT,
                metadata JSON
            )
        """)

        # Create gate_decisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gate_decisions (
                decision_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                intent TEXT NOT NULL,
                decision TEXT NOT NULL,
                confidence REAL NOT NULL,
                metrics JSON NOT NULL,
                rationale JSON NOT NULL,
                created_at TEXT NOT NULL,
                series_id TEXT,
                suggested_action TEXT
            )
        """)

        # Create queries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                query_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                query_text TEXT NOT NULL,
                intent TEXT NOT NULL,
                findings_ids JSON NOT NULL,
                gate_decision_id TEXT,
                created_at TEXT NOT NULL,
                series_id TEXT,
                player_id TEXT,
                FOREIGN KEY(gate_decision_id) REFERENCES gate_decisions(decision_id)
            )
        """)

        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_findings_session ON findings(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_findings_intent ON findings(intent)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_findings_series ON findings(series_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gate_session ON gate_decisions(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gate_intent ON gate_decisions(intent)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gate_decision ON gate_decisions(decision)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_queries_session ON queries(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_queries_intent ON queries(intent)
        """)

        conn.commit()
        conn.close()

    # ============ Findings Operations ============

    def store_finding(self, finding: DerivedFinding) -> bool:
        """Store a derived finding."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO findings (
                    finding_id, session_id, intent, fact_type, content,
                    confidence, created_at, series_id, player_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                finding.finding_id,
                finding.session_id,
                finding.intent,
                finding.fact_type,
                json.dumps(finding.content),
                finding.confidence,
                finding.created_at,
                finding.series_id,
                finding.player_id,
                json.dumps(finding.metadata or {}),
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error storing finding: {e}")
            return False

    def get_findings_by_session(self, session_id: str) -> List[DerivedFinding]:
        """Get all findings for a session."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM findings WHERE session_id = ? ORDER BY created_at DESC
        """, (session_id,))

        rows = cursor.fetchall()
        conn.close()

        return [
            DerivedFinding(
                finding_id=row["finding_id"],
                session_id=row["session_id"],
                intent=row["intent"],
                fact_type=row["fact_type"],
                content=json.loads(row["content"]),
                confidence=row["confidence"],
                created_at=row["created_at"],
                series_id=row["series_id"],
                player_id=row["player_id"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
            for row in rows
        ]

    def get_findings_by_intent(self, intent: str, limit: int = 10) -> List[DerivedFinding]:
        """Get recent findings for a specific intent."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM findings
            WHERE intent = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (intent, limit))

        rows = cursor.fetchall()
        conn.close()

        return [
            DerivedFinding(
                finding_id=row["finding_id"],
                session_id=row["session_id"],
                intent=row["intent"],
                fact_type=row["fact_type"],
                content=json.loads(row["content"]),
                confidence=row["confidence"],
                created_at=row["created_at"],
                series_id=row["series_id"],
                player_id=row["player_id"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
            for row in rows
        ]

    # ============ Gate Decision Operations ============

    def store_gate_decision(self, decision: GateDecisionRecord) -> bool:
        """Store a gate decision record."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO gate_decisions (
                    decision_id, session_id, intent, decision, confidence,
                    metrics, rationale, created_at, series_id, suggested_action
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.decision_id,
                decision.session_id,
                decision.intent,
                decision.decision,
                decision.confidence,
                json.dumps(decision.metrics),
                json.dumps(decision.rationale),
                decision.created_at,
                decision.series_id,
                decision.suggested_action,
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error storing gate decision: {e}")
            return False

    def get_gate_decision_stats(self, intent: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about gate decisions.

        Returns:
            Dict with historical_hit_rate and recent_failure_rate
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if intent:
            cursor.execute("""
                SELECT decision, COUNT(*) as count
                FROM gate_decisions
                WHERE intent = ?
                GROUP BY decision
            """, (intent,))
        else:
            cursor.execute("""
                SELECT decision, COUNT(*) as count
                FROM gate_decisions
                GROUP BY decision
            """)

        rows = cursor.fetchall()
        conn.close()

        stats = {row["decision"]: row["count"] for row in rows}

        total = sum(stats.values())
        if total == 0:
            return {"historical_hit_rate": 0.5, "recent_failure_rate": 0.0}

        # Hit rate = ACCEPT / (ACCEPT + LOW_CONFIDENCE + REJECT)
        # We treat LOW_CONFIDENCE as partial hit
        accept_count = stats.get("accept", 0)
        low_conf_count = stats.get("low_confidence", 0)
        reject_count = stats.get("reject", 0)

        historical_hit_rate = (accept_count + 0.5 * low_conf_count) / total
        recent_failure_rate = reject_count / total

        return {
            "historical_hit_rate": historical_hit_rate,
            "recent_failure_rate": recent_failure_rate,
            "total_decisions": total,
        }

    # ============ Query Operations ============

    def store_query(self, query: QueryRecord) -> bool:
        """Store a query record."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO queries (
                    query_id, session_id, query_text, intent, findings_ids,
                    gate_decision_id, created_at, series_id, player_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                query.query_id,
                query.session_id,
                query.query_text,
                query.intent,
                json.dumps(query.findings_ids),
                query.gate_decision_id,
                query.created_at,
                query.series_id,
                query.player_id,
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error storing query: {e}")
            return False

    def find_similar_queries(
        self,
        query_text: str,
        intent: Optional[str] = None,
        limit: int = 5
    ) -> List[QueryRecord]:
        """
        Find similar historical queries.

        For now, does exact intent match. Can be enhanced with similarity search.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if intent:
            cursor.execute("""
                SELECT * FROM queries
                WHERE intent = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (intent, limit))
        else:
            cursor.execute("""
                SELECT * FROM queries
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [
            QueryRecord(
                query_id=row["query_id"],
                session_id=row["session_id"],
                query_text=row["query_text"],
                intent=row["intent"],
                findings_ids=json.loads(row["findings_ids"]),
                gate_decision_id=row["gate_decision_id"],
                created_at=row["created_at"],
                series_id=row["series_id"],
                player_id=row["player_id"],
            )
            for row in rows
        ]

    # ============ Utility Functions ============

    @staticmethod
    def generate_id() -> str:
        """Generate a unique ID."""
        import uuid
        return str(uuid.uuid4())

    @staticmethod
    def now() -> str:
        """Get current ISO timestamp."""
        return datetime.utcnow().isoformat()

    def clear_session(self, session_id: str) -> bool:
        """Clear all data for a session."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM findings WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM gate_decisions WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM queries WHERE session_id = ?", (session_id,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error clearing session: {e}")
            return False


# ============ Integration Helpers ============

def gate_result_to_record(
    result: GateResult,
    session_id: str,
    intent: str,
    series_id: Optional[str] = None,
) -> GateDecisionRecord:
    """Convert a GateResult to a GateDecisionRecord for storage."""
    return GateDecisionRecord(
        decision_id=MemoryStore.generate_id(),
        session_id=session_id,
        intent=intent,
        decision=result.decision.value,
        confidence=result.confidence,
        metrics=result.score_breakdown,
        rationale=result.rationale,
        created_at=MemoryStore.now(),
        series_id=series_id,
        suggested_action=result.suggested_action,
    )
