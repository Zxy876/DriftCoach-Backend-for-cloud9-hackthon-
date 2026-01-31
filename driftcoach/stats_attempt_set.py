from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from driftcoach.stats.spec import StatsQuerySpec


class StatsAttemptSet:
    """Lightweight scheduler for statistics-feed attempts."""

    _deferred_keys: List[str] = []

    def __init__(self, max_per_run: int = 2) -> None:
        self.max_per_run = max_per_run

    @staticmethod
    def _canonical_list(value: Any) -> List[str]:
        if isinstance(value, list):
            items = value
        elif value is None:
            items = []
        else:
            items = [value]
        return [str(v) for v in items if v is not None and str(v) != ""]

    def _normalize_entities(self, mining_summary: Any, fallback_entities: Optional[Dict[str, List[str]]] = None) -> Dict[str, List[str]]:
        discovered: Dict[str, Any] = {}
        seeds: Dict[str, Any] = {}

        if mining_summary is not None:
            if isinstance(mining_summary, dict):
                discovered = mining_summary.get("discovered") or mining_summary.get("entity_counts") or {}
                seeds = mining_summary.get("seeds") or {}
            else:
                discovered = getattr(mining_summary, "discovered", {}) or getattr(mining_summary, "entity_counts", {}) or {}
                seeds = getattr(mining_summary, "seeds", {}) or {}

        if fallback_entities:
            for k, v in fallback_entities.items():
                if k not in discovered or not discovered.get(k):
                    discovered[k] = v

        entities = {
            "players": self._canonical_list(discovered.get("players")),
            "teams": self._canonical_list(discovered.get("teams")),
            "tournaments": self._canonical_list(discovered.get("tournaments")),
            "series": self._canonical_list(discovered.get("series")),
        }

        for bucket, vals in seeds.items():
            if bucket not in entities:
                continue
            for v in self._canonical_list(vals):
                if v not in entities[bucket]:
                    entities[bucket].append(v)

        return entities

    @staticmethod
    def _candidate_key(spec: StatsQuerySpec) -> str:
        payload = json.dumps([spec.target, spec.target_id, spec.time_window, spec.tournament_ids], sort_keys=True, default=str)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _build_candidate(spec: StatsQuerySpec, priority: int, source: str) -> Dict[str, Any]:
        return {
            "target": spec.target,
            "spec": spec,
            "priority": priority,
            "source": source,
            "candidate_key": StatsAttemptSet._candidate_key(spec),
        }

    def _apply_deferred_rotation(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self._deferred_keys:
            return candidates
        deferred_set = set(self._deferred_keys)
        fresh = [c for c in candidates if c["candidate_key"] not in deferred_set]
        deferred = [c for c in candidates if c["candidate_key"] in deferred_set]
        return fresh + deferred

    def _collect_candidates(self, entities: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        players = entities.get("players") or []
        teams = entities.get("teams") or []
        tournaments = entities.get("tournaments") or []

        candidates: List[Dict[str, Any]] = []

        if players:
            for idx, pid in enumerate(players):
                spec = StatsQuerySpec(target="player", target_id=pid, time_window="LAST_3_MONTHS")
                candidates.append(self._build_candidate(spec, priority=100 - idx, source="player"))

        if teams:
            for idx, tid in enumerate(teams):
                spec = StatsQuerySpec(target="team", target_id=tid, time_window="LAST_3_MONTHS")
                candidates.append(self._build_candidate(spec, priority=80 - idx, source="team"))

        if tournaments:
            tournament_slice = tournaments[:2]
            if players:
                for pid in players[:2]:
                    spec = StatsQuerySpec(target="player", target_id=pid, tournament_ids=tournament_slice)
                    candidates.append(self._build_candidate(spec, priority=60, source="player+tournament"))
            if teams:
                for tid in teams[:2]:
                    spec = StatsQuerySpec(target="team", target_id=tid, tournament_ids=tournament_slice)
                    candidates.append(self._build_candidate(spec, priority=50, source="team+tournament"))

        seen: set[str] = set()
        deduped: List[Dict[str, Any]] = []
        for cand in sorted(candidates, key=lambda c: c["priority"], reverse=True):
            key = cand["candidate_key"]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cand)
        return deduped

    def build(self, research_plan: Any, mining_summary: Any, fallback_entities: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
        entities = self._normalize_entities(mining_summary, fallback_entities=fallback_entities)
        all_candidates = self._collect_candidates(entities)
        rotated = self._apply_deferred_rotation(all_candidates)
        queue = rotated[: self.max_per_run]
        return {"queue": queue, "all_candidates": rotated, "entities": entities}

    @classmethod
    def mark_deferred(cls, candidate_key: str) -> None:
        if candidate_key and candidate_key not in cls._deferred_keys:
            cls._deferred_keys.append(candidate_key)
            if len(cls._deferred_keys) > 20:
                cls._deferred_keys = cls._deferred_keys[-20:]

    @classmethod
    def clear_deferred(cls, candidate_key: str) -> None:
        if candidate_key in cls._deferred_keys:
            cls._deferred_keys = [k for k in cls._deferred_keys if k != candidate_key]
