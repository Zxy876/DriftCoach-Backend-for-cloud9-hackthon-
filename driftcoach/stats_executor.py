from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict
from typing import Any, Dict, List, Tuple

import requests

from driftcoach.core.state import State
from driftcoach.stats.spec import StatsQuerySpec
from driftcoach.stats.grammar import StatsGrammar

STATISTICS_FEED_URL = os.getenv("STATISTICS_FEED_URL", "https://api-op.grid.gg/statistics-feed/graphql")


class _StatsCacheEntry:
    def __init__(self, result: Dict[str, Any], states: List[State], expires_at: float) -> None:
        self.result = result
        self.states = states
        self.expires_at = expires_at


class StatsExecutor:
    """Single-shot executor for statistics-feed GraphQL queries with in-memory cache."""

    cache_ttl_seconds = 600.0
    timeout_seconds = float(os.getenv("STATS_HTTP_TIMEOUT", "60"))
    _cache: Dict[str, _StatsCacheEntry] = {}

    def __init__(self, api_key: str | None = None, endpoint: str | None = None) -> None:
        self.api_key = api_key
        self.endpoint = endpoint or STATISTICS_FEED_URL
        self._executed = False

    @staticmethod
    def _cache_key(query: str, variables: Dict[str, Any]) -> str:
        payload = json.dumps({"q": query, "v": variables}, sort_keys=True, default=str)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _cache_get(cls, key: str) -> Tuple[Dict[str, Any] | None, List[State] | None]:
        entry = cls._cache.get(key)
        if entry and time.time() < entry.expires_at:
            return entry.result, entry.states
        if entry:
            cls._cache.pop(key, None)
        return None, None

    @classmethod
    def _cache_set(cls, key: str, result: Dict[str, Any], states: List[State]) -> None:
        cls._cache[key] = _StatsCacheEntry(result, states, time.time() + cls.cache_ttl_seconds)

    def run_once(self, spec: StatsQuerySpec) -> Tuple[Dict[str, Any], List[State]]:
        def _fail(status: str, reason: str) -> Tuple[Dict[str, Any], List[State]]:
            return {"patch": "STATS_EXECUTOR", "status": status, "reason": reason, "origin": "stats-executor", "target": getattr(spec, "target", None), "spec": asdict(spec) if isinstance(spec, StatsQuerySpec) else None}, []

        if self._executed:
            return _fail("skipped", "already_executed")
        self._executed = True

        if not isinstance(spec, StatsQuerySpec) or not spec.is_valid():
            return _fail("invalid_spec", "stats_query_spec_invalid")

        if not self.api_key:
            return _fail("unavailable", "missing_api_key")

        try:
            query, variables = StatsGrammar.compile(spec)
        except Exception:
            return _fail("invalid_spec", "stats_query_spec_invalid")

        cache_key = self._cache_key(query, variables)
        cached_result, cached_states = self._cache_get(cache_key)
        if cached_result is not None and cached_states is not None:
            return cached_result, cached_states

        headers = {"x-api-key": self.api_key, "Content-Type": "application/json"}
        try:
            resp = requests.post(
                self.endpoint,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("errors"):
                return _fail("unavailable", str(data.get("errors")))
            stats_node = None
            target = spec.target
            if target == "player":
                stats_node = (data.get("data", {}) or {}).get("playerStatistics") if isinstance(data, dict) else None
            elif target == "team":
                stats_node = (data.get("data", {}) or {}).get("teamStatistics") if isinstance(data, dict) else None
            states = []
            aggregation_series_ids = (stats_node or {}).get("aggregationSeriesIds") if isinstance(stats_node, dict) else []
            if stats_node and aggregation_series_ids:
                status = "success"
                state = self._to_state(spec, stats_node)
                states.append(state)
                result = {
                    "patch": "STATS_EXECUTOR",
                    "status": status,
                    "reason": "executed",
                    "origin": "stats-executor",
                    "target": target,
                    "spec": asdict(spec),
                }
                self._cache_set(cache_key, result, states)
                return result, states
            return _fail("unavailable", "aggregation_missing")
        except Exception as exc:  # pragma: no cover
            return _fail("unavailable", str(exc))

    @staticmethod
    def _to_state(spec: StatsQuerySpec, payload: Dict[str, Any]) -> State:
        aggregation_series_ids = payload.get("aggregationSeriesIds") or []
        series = payload.get("series") or {}
        game = payload.get("game") or {}
        kills = series.get("kills") or {}
        wins_raw = game.get("wins") if isinstance(game, dict) else None
        if isinstance(wins_raw, list):
            win_entry = next((w for w in wins_raw if isinstance(w, dict) and w.get("value") is True), None)
            win_percentage = win_entry.get("percentage") if win_entry else None
        elif isinstance(wins_raw, dict):
            win_percentage = wins_raw.get("percentage")
        else:
            win_percentage = None
        series_count = series.get("count") or 0
        game_count = game.get("count") or 0
        perf = {
            "kills_per_map": {
                "value": kills.get("avg"),
                "baseline": kills.get("avg"),
                "delta": 0.0,
                "sample": game_count,
            },
            "win_rate": {
                "value": win_percentage,
                "baseline": win_percentage,
                "delta": 0.0,
                "sample": game_count,
            },
            "rating": {"value": None, "baseline": None, "delta": None, "sample": None},
        }
        trend = payload.get("trend") or {}
        sample = {
            "series_count": series_count,
            "map_count": game_count,
            "round_count": None,
        }
        scope = {"level": spec.target}
        if spec.target == "player":
            scope["playerId"] = str(spec.target_id)
            subject_id = str(spec.target_id)
        else:
            scope["teamId"] = str(spec.target_id)
            subject_id = str(spec.target_id)

        agg_payload = {
            "aggregationSeriesIds": aggregation_series_ids,
            "mock": False,
            "timeWindow": spec.time_window,
            "tournamentIds": spec.tournament_ids,
            "scope": scope,
            "sample": sample,
            "performance": perf,
            "trend": trend,
            "context": {},
        }
        filter_meta = {
            "timeWindow": spec.time_window,
            "tournamentIds": spec.tournament_ids,
            "mock": False,
            "source": "statistics-feed",
        }
        state_id_raw = json.dumps([spec.target, scope, filter_meta], sort_keys=True)
        state_id = hashlib.sha1(state_id_raw.encode("utf-8")).hexdigest()[:16]
        extras = {
            "evidence_type": "AGGREGATED_PERFORMANCE",
            "aggregation_level": spec.target,
            "aggregation_series_ids": aggregation_series_ids,
            "aggregation_unavailable": not bool(payload) or not aggregation_series_ids,
            "aggregation_raw": payload,
            "filter_used": filter_meta,
            "trace_id": "stats-feed",
            "mock": False,
            "note": "statistics_feed",
        }
        return State(
            state_id=state_id,
            series_id=subject_id,
            game_index=0,
            timestamp=0.0,
            map="context",
            score_diff=0,
            econ_diff=0,
            alive_diff=0,
            ult_diff=0,
            objective_context=None,
            phase="CONTEXT",
            extras=extras,
        )
