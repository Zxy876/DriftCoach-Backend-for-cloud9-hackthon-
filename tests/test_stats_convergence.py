from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Any, Callable

import pytest
import requests

from driftcoach.api import _run_ai_mode
from driftcoach.adapters.grid import queries as q
from driftcoach.adapters.grid.client import GridClient, clear_response_cache
from driftcoach.adapters.grid.rate_budget import (
    set_run_budget,
    clear_run_budget,
    reset_grid_controls,
    grid_health_snapshot,
)
from driftcoach.stats_attempt_set import StatsAttemptSet
from driftcoach.stats.spec import StatsQuerySpec


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")
        return None


def _mock_stats_payload(target: str) -> Dict[str, Any]:
    node_key = "playerStatistics" if target in {"PLAYER_STATS", "player"} else "teamStatistics"
    return {
        "data": {
            node_key: {
                "aggregationSeriesIds": ["mock-series-1"],
                "series": {"count": 4, "kills": {"sum": 40, "min": 8, "max": 12, "avg": 10.0}},
                "game": {"count": 8, "wins": {"value": 5, "count": 5, "percentage": 0.625, "streak": {"min": 1, "max": 3, "current": 2}}},
                "segment": {"type": "map", "count": 8, "deaths": {"sum": 60, "min": 5, "max": 10, "avg": 7.5}},
                "trend": {"winRate": {"slope": 0.05}},
            }
        }
    }


@contextmanager
def stub_requests(stats_ok: bool = True, stats_target: str = "player"):
    """Stub Grid and statistics-feed GraphQL endpoints."""
    original_post = requests.post

    def _fake_post(url, json=None, headers=None, timeout=30):  # type: ignore
        body = json or {}
        query = body.get("query", "")
        vars_payload = body.get("variables", {}) or {}
        now = datetime.now(timezone.utc).isoformat()

        # Grid queries
        if query == q.Q_SERIES_BY_ID:
            payload = {
                "data": {
                    "series": {
                        "id": vars_payload.get("id", "mock-series"),
                        "startTimeScheduled": now,
                        "format": {"name": "BO3"},
                        "tournament": {"nameShortened": "MockCup"},
                        "teams": [
                            {"baseInfo": {"id": "79", "name": "MockTeamA"}},
                            {"baseInfo": {"id": "99", "name": "MockTeamB"}},
                        ],
                    }
                }
            }
            return _FakeResponse(payload)
        if query == q.Q_ALL_SERIES_WINDOW:
            payload = {
                "data": {
                    "allSeries": {
                        "edges": [
                            {
                                "node": {
                                    "id": "mock-series-0",
                                    "startTimeScheduled": now,
                                    "format": {"name": "BO3"},
                                    "tournament": {"nameShortened": "MockCup"},
                                    "teams": [
                                        {"baseInfo": {"id": "79", "name": "MockTeamA"}},
                                        {"baseInfo": {"id": "99", "name": "MockTeamB"}},
                                    ],
                                }
                            }
                        ],
                        "pageInfo": {"hasNextPage": False},
                    }
                }
            }
            return _FakeResponse(payload)
        if query == q.Q_TEAM_ROSTER:
            return _FakeResponse({"data": {"players": {"edges": []}}})

        # statistics-feed (match by keywords)
        if "playerStatistics" in query:
            return _FakeResponse(_mock_stats_payload(stats_target) if stats_ok else {"data": {"playerStatistics": None}})
        if "teamStatistics" in query:
            return _FakeResponse(_mock_stats_payload(stats_target) if stats_ok else {"data": {"teamStatistics": None}})

        return _FakeResponse({"data": {}})

    requests.post = _fake_post
    try:
        yield
    finally:
        requests.post = original_post


def _run_once(max_steps: int = 1) -> Dict[str, Any]:
    payload = _run_ai_mode(
        states=[],
        context_meta={},
        coach_query="性能稳定性分析",
        anchor_team_id=None,
        grid_api_key=os.getenv("GRID_API_KEY", "mock-key"),
        grid_player_id=os.getenv("GRID_PLAYER_ID", "91"),
        grid_series_id=os.getenv("GRID_SERIES_ID", "2819676"),
        data_source="grid",
        max_steps=max_steps,
    )
    return payload


@pytest.fixture(autouse=True)
def _reset_env():
    os.environ.setdefault("DATA_SOURCE", "grid")
    os.environ.setdefault("GRID_FAULT_MODE", "NONE")
    reset_grid_controls()
    clear_response_cache()
    yield
    clear_run_budget()


def _extract_core(payload: Dict[str, Any]) -> Dict[str, Any]:
    ai = payload.get("ai", {})
    return {
        "answer": ai.get("answer"),
        "research_progress": ai.get("research_progress"),
        "stats_results": ai.get("stats_results"),
        "stats_attempts": ai.get("stats_attempts"),
        "grid_health": ai.get("grid_health") or payload.get("context", {}).get("grid_health"),
        "aggregated_performance": payload.get("context", {}).get("aggregated_performance"),
    }


def _dump(label: str, core: Dict[str, Any]) -> None:
    try:
        import json
        with open(f"/tmp/{label}.json", "w") as f:
            json.dump(core, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def test_case_a_stats_reachable():
    set_run_budget(5)
    with stub_requests(stats_ok=True):
        payload = _run_once(max_steps=2)
    core = _extract_core(payload)
    _dump("case_a_stats_reachable", core)

    assert core["research_progress"]["can_answer"] is True
    assert core["stats_results"][0]["status"] == "success"
    assert core["stats_results"][0]["target"] == "player"
    assert "baseline" not in core["research_progress"]["missing_axes"]
    assert core["aggregated_performance"] is not None
    assert "非高置信" not in (core["answer"] or "")


def test_case_b_stats_blocked_by_budget():
    set_run_budget(0)
    os.environ["GRID_FAULT_MODE"] = "429"
    with stub_requests(stats_ok=True):
        payload = _run_once(max_steps=1)
    core = _extract_core(payload)
    _dump("case_b_stats_blocked", core)

    assert core["stats_results"][0]["status"] == "skipped"
    assert core["stats_results"][0]["reason"] in {"grid_budget_exhausted", "circuit_open"}
    assert core["research_progress"]["can_answer"] is False
    assert "非高置信" in (core["answer"] or "")
    assert core["aggregated_performance"] is None


def test_case_c_candidate_rotation(monkeypatch):
    # Build two candidates manually to force rotation
    cand_player = {
        "target": "player",
        "spec": StatsQuerySpec(target="player", target_id="91", time_window="LAST_3_MONTHS"),
        "candidate_key": "cand-player",
        "priority": 100,
        "source": "player",
    }
    cand_team = {
        "target": "team",
        "spec": StatsQuerySpec(target="team", target_id="79", time_window="LAST_3_MONTHS"),
        "candidate_key": "cand-team",
        "priority": 90,
        "source": "team",
    }
    calls = {"n": 0}

    def fake_build(self, research_plan, mining_summary, fallback_entities=None):  # type: ignore[override]
        calls["n"] += 1
        if calls["n"] == 1:
            return {"queue": [cand_player, cand_team], "all_candidates": [cand_player, cand_team], "entities": {}}
        return {"queue": [cand_team, cand_player], "all_candidates": [cand_team, cand_player], "entities": {}}

    monkeypatch.setattr(StatsAttemptSet, "build", fake_build)

    # First run: budget exhausted, player candidate deferred
    set_run_budget(0)
    with stub_requests(stats_ok=True):
        payload1 = _run_once(max_steps=1)
    core1 = _extract_core(payload1)
    _dump("case_c_run1", core1)
    assert core1["stats_attempts"][0]["status"] == "deferred"

    # Second run: budget open, team candidate succeeds
    set_run_budget(5)
    with stub_requests(stats_ok=True, stats_target="team"):
        payload2 = _run_once(max_steps=1)
    core2 = _extract_core(payload2)
    _dump("case_c_run2", core2)

    assert len(core2["stats_attempts"]) >= 2
    # ensure second attempt includes success
    assert any(att.get("result", {}).get("status") == "success" for att in core2["stats_attempts"]) or any(
        att.get("status") == "attempted_ok" for att in core2["stats_attempts"]
    )
    assert core2["aggregated_performance"] is not None
    assert core2["research_progress"]["can_answer"] is True


if __name__ == "__main__":
    import pytest as _pytest

    _pytest.main([__file__])
