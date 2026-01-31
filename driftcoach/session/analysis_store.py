from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib
import json


@dataclass
class SessionAnalysisNode:
    node_id: str
    type: str
    source: str
    axes_covered: List[str]
    confidence: float
    created_from_query: str
    created_at: str
    last_updated_at: str
    target: Optional[str] = None
    window: Optional[str] = None
    used_in_queries: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionStatsSnapshot:
    target: str
    window: Optional[str]
    used_in_queries: List[str]
    last_status: str
    last_updated_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionAnalysis:
    session_id: str
    entities: Dict[str, Set[str]]
    analysis_nodes: List[SessionAnalysisNode]
    stats_snapshots: List[SessionStatsSnapshot]
    last_query: Optional[str] = None
    last_updated_at: Optional[str] = None
    recently_added_node_ids: List[str] = field(default_factory=list)


class SessionAnalysisStore:
    def __init__(self) -> None:
        self._store: Dict[str, SessionAnalysis] = {}

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat() + "Z"

    @staticmethod
    def _node_key(node: SessionAnalysisNode) -> Tuple[str, Optional[str], Optional[str]]:
        return node.type, node.target, node.window

    def init_session(self, session_id: str) -> None:
        if session_id in self._store:
            return
        self._store[session_id] = SessionAnalysis(
            session_id=session_id,
            entities={"players": set(), "teams": set(), "series": set(), "tournaments": set()},
            analysis_nodes=[],
            stats_snapshots=[],
            last_query=None,
            last_updated_at=self._now(),
        )

    def _ensure(self, session_id: str) -> SessionAnalysis:
        if session_id not in self._store:
            self.init_session(session_id)
        return self._store[session_id]

    def merge_entities(self, session_id: str, entities: Dict[str, List[str]]) -> None:
        session = self._ensure(session_id)
        for k in ["players", "teams", "series", "tournaments"]:
            current = session.entities.setdefault(k, set())
            for v in entities.get(k, []) or []:
                if v:
                    current.add(str(v))
        session.last_updated_at = self._now()

    def upsert_nodes(self, session_id: str, nodes: List[Dict[str, Any]], query: str) -> List[str]:
        session = self._ensure(session_id)
        session.recently_added_node_ids = []
        if not nodes:
            return []
        existing_by_key: Dict[Tuple[str, Optional[str], Optional[str]], SessionAnalysisNode] = {
            self._node_key(n): n for n in session.analysis_nodes
        }
        for node_dict in nodes:
            # sanitize
            node = SessionAnalysisNode(**node_dict)
            if node.type == "AGGREGATED_PERFORMANCE" and node.source == "stats":
                raw_present = bool((node.metadata or {}).get("raw_present"))
                agg_ids = node.metadata.get("aggregation_series_ids") if isinstance(node.metadata, dict) else None
                if not raw_present or not agg_ids:
                    # Skip empty stats nodes to avoid false accumulation
                    continue
            key = self._node_key(node)
            if key in existing_by_key:
                existing = existing_by_key[key]
                merged_axes = list({*existing.axes_covered, *node.axes_covered})
                merged_conf = max(existing.confidence, node.confidence)
                merged_used = list({*existing.used_in_queries, *node.used_in_queries})
                existing.axes_covered = merged_axes
                existing.confidence = merged_conf
                existing.used_in_queries = merged_used
                existing.last_updated_at = self._now()
                existing.metadata = {**existing.metadata, **node.metadata}
            else:
                node.used_in_queries = list({*node.used_in_queries, query})
                session.analysis_nodes.append(node)
                session.recently_added_node_ids.append(node.node_id)
                existing_by_key[key] = node
        session.last_query = query
        session.last_updated_at = self._now()
        return session.recently_added_node_ids

    def upsert_stats_snapshots(
        self, session_id: str, snapshots: List[Dict[str, Any]], query: str, status: str
    ) -> None:
        session = self._ensure(session_id)
        if not snapshots:
            return
        existing: Dict[Tuple[str, Optional[str]], SessionStatsSnapshot] = {
            (s.target, s.window): s for s in session.stats_snapshots
        }
        for snap in snapshots:
            key = (snap.get("target"), snap.get("window"))
            if key in existing:
                cur = existing[key]
                cur.used_in_queries = list({*cur.used_in_queries, query})
                cur.last_status = status
                cur.last_updated_at = self._now()
                cur.metadata = {**cur.metadata, **(snap.get("metadata") or {})}
            else:
                session.stats_snapshots.append(
                    SessionStatsSnapshot(
                        target=snap.get("target"),
                        window=snap.get("window"),
                        used_in_queries=[query],
                        last_status=status,
                        last_updated_at=self._now(),
                        metadata=snap.get("metadata") or {},
                    )
                )
        session.last_query = query
        session.last_updated_at = self._now()

    def snapshot(self, session_id: str) -> Dict[str, Any]:
        session = self._ensure(session_id)
        return {
            "session_id": session.session_id,
            "entities": {k: sorted(list(v)) for k, v in session.entities.items()},
            "analysis_nodes": [
                {
                    "node_id": n.node_id,
                    "type": n.type,
                    "source": n.source,
                    "axes_covered": n.axes_covered,
                    "confidence": n.confidence,
                    "created_from_query": n.created_from_query,
                    "created_at": n.created_at,
                    "last_updated_at": n.last_updated_at,
                    "target": n.target,
                    "window": n.window,
                    "used_in_queries": n.used_in_queries,
                    "metadata": n.metadata,
                }
                for n in sorted(session.analysis_nodes, key=lambda x: x.last_updated_at)
            ],
            "stats_snapshots": [
                {
                    "target": s.target,
                    "window": s.window,
                    "used_in_queries": s.used_in_queries,
                    "last_status": s.last_status,
                    "last_updated_at": s.last_updated_at,
                    "metadata": s.metadata,
                }
                for s in sorted(session.stats_snapshots, key=lambda x: x.last_updated_at)
            ],
            "last_query": session.last_query,
            "last_updated_at": session.last_updated_at,
            "recently_added_node_ids": list(session.recently_added_node_ids),
        }


def _confidence_from_sample(sample: Optional[int]) -> float:
    if sample is None:
        return 0.55
    if sample >= 80:
        return 0.9
    if sample >= 40:
        return 0.8
    if sample >= 20:
        return 0.7
    return 0.55 + min(sample / 100.0, 0.15)


def build_analysis_node_from_agg(
    agg: Dict[str, Any],
    coach_query: str,
    source: str = "stats",
    target: Optional[str] = None,
) -> SessionAnalysisNode:
    filt = agg.get("filter_used") or {}
    axes: List[str] = ["baseline"]
    window = None
    if filt.get("timeWindow"):
        axes.append("time")
        window = str(filt.get("timeWindow"))
    if filt.get("tournamentIds"):
        axes.append("opponent")
    level = agg.get("aggregation_level")
    if level:
        axes.append(level)
    sample = None
    raw = agg.get("raw") or {}
    sample = (raw.get("series") or {}).get("count") or (raw.get("game") or {}).get("count")
    confidence = _confidence_from_sample(sample)
    node_id_raw = json.dumps([target or level or "agg", window, axes], sort_keys=True, default=str)
    node_id = hashlib.sha1(node_id_raw.encode("utf-8")).hexdigest()[:10]
    now = SessionAnalysisStore._now()
    return SessionAnalysisNode(
        node_id=node_id,
        type="AGGREGATED_PERFORMANCE",
        source=source,
        axes_covered=axes,
        confidence=confidence,
        created_from_query=coach_query,
        created_at=now,
        last_updated_at=now,
        target=target or level,
        window=window,
        used_in_queries=[coach_query],
        metadata={
            "sample": sample,
            "filter_used": filt,
            "note": agg.get("note"),
            "raw_present": bool(raw),
            "aggregation_series_ids": agg.get("aggregation_series_ids"),
        },
    )


def build_snapshot_from_stats_results(stats_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    snaps: List[Dict[str, Any]] = []
    for r in stats_results:
        target = r.get("target") or "UNKNOWN"
        window = None
        snaps.append({"target": target, "window": window, "metadata": {"status": r.get("status"), "reason": r.get("reason")}})
    return snaps


session_analysis_store = SessionAnalysisStore()
