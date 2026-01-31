"""
Ad-hoc resilience harness (no FastAPI). Executes _run_ai_mode under different GRID_FAULT_MODE
settings and prints Grid health counters + answer tail.

Cases:
- A: fault=429
- B: fault=EOF
- C: fault=NONE with RunBudget=2 (3rd call blocked)
- D: fault=NONE with cache warm/hit
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone

import requests

from driftcoach.api import _run_ai_mode
from driftcoach.adapters.grid import queries as q
from driftcoach.adapters.grid.client import GridClient, clear_response_cache
from driftcoach.adapters.grid.rate_budget import (
    set_run_budget,
    clear_run_budget,
    reset_debug_counters,
    grid_health_snapshot,
    reset_grid_controls,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload
        self.status_code = 200
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


@contextmanager
def stub_requests():
    original_post = requests.post

    def _fake_post(url, json=None, headers=None, timeout=30):  # type: ignore
        body = json or {}
        query = body.get("query", "")
        vars_payload = body.get("variables", {}) or {}
        now = datetime.now(timezone.utc).isoformat()
        if query == q.Q_SERIES_BY_ID:
            payload = {
                "data": {
                    "series": {
                        "id": vars_payload.get("id", "mock-series"),
                        "startTimeScheduled": now,
                        "format": {"name": "BO3"},
                        "tournament": {"nameShortened": "MockCup"},
                        "teams": [
                            {"baseInfo": {"id": "mock-team-a", "name": "MockTeamA"}},
                            {"baseInfo": {"id": "mock-team-b", "name": "MockTeamB"}},
                        ],
                    }
                }
            }
            return _FakeResponse(payload)
        if query == q.Q_ALL_SERIES_WINDOW:
            edges = [
                {
                    "node": {
                        "id": "mock-series-0",
                        "startTimeScheduled": now,
                        "format": {"name": "BO3"},
                        "tournament": {"nameShortened": "MockCup"},
                        "teams": [
                            {"baseInfo": {"id": "mock-team-a", "name": "MockTeamA"}},
                            {"baseInfo": {"id": "mock-team-b", "name": "MockTeamB"}},
                        ],
                    }
                }
            ]
            payload = {"data": {"allSeries": {"edges": edges, "pageInfo": {"hasNextPage": False}}}}
            return _FakeResponse(payload)
        if query == q.Q_TEAM_ROSTER:
            return _FakeResponse({"data": {"players": {"edges": []}}})
        if query == getattr(q, "Q_PLAYER_STATISTICS", ""):
            payload = {
                "data": {
                    "playerStatistics": {
                        "aggregationSeriesIds": ["mock-series-1"],
                        "series": {"count": 1, "kills": {"sum": 10, "min": 5, "max": 10, "avg": 7.5}},
                        "game": {"count": 3, "wins": {"value": 2, "count": 2, "percentage": 0.66, "streak": {"min": 1, "max": 2, "current": 1}}},
                        "segment": {"type": "map", "count": 3, "deaths": {"sum": 20, "min": 5, "max": 10, "avg": 6.6}},
                    }
                }
            }
            return _FakeResponse(payload)
        if query == getattr(q, "Q_TEAM_STATISTICS", ""):
            payload = {
                "data": {
                    "teamStatistics": {
                        "aggregationSeriesIds": ["mock-series-1"],
                        "series": {"count": 1, "kills": {"sum": 10, "min": 5, "max": 10, "avg": 7.5}},
                        "game": {"count": 3, "wins": {"value": 2, "count": 2, "percentage": 0.66, "streak": {"min": 1, "max": 2, "current": 1}}},
                        "segment": {"type": "map", "count": 3, "deaths": {"sum": 20, "min": 5, "max": 10, "avg": 6.6}},
                    }
                }
            }
            return _FakeResponse(payload)
        return _FakeResponse({"data": {}})

    requests.post = _fake_post
    try:
        yield
    finally:
        requests.post = original_post


def _print_case(label: str, payload: dict | None, err: str | None = None):
    health = grid_health_snapshot()
    counters = health.get("debug_counters", {})
    answer = ((payload or {}).get("ai", {}).get("answer") or err or "")
    tail = answer[-200:]
    print(
        f"[{label}] state={health.get('circuit_state')} calls_sent={counters.get('calls_sent')} "
        f"cache_hit={counters.get('cache_hit')} cache_miss={counters.get('cache_miss')} "
        f"denied(rate/run/circuit)={counters.get('rate_budget_denied')}/"
        f"{counters.get('run_budget_denied')}/{counters.get('circuit_open_denied')} tail={tail}"
    )


def run_case(label: str, fault: str, run_budget: int = 2, double_run: bool = False, trigger_third_call: bool = False):
    os.environ["GRID_FAULT_MODE"] = fault
    reset_grid_controls()
    clear_response_cache()
    payload = None
    err = None
    with stub_requests():
        set_run_budget(run_budget)
        try:
            payload = _run_ai_mode(
                states=[],
                context_meta={},
                coach_query=f"Grid resilience {label}",
                anchor_team_id=None,
                grid_api_key=os.getenv("GRID_API_KEY", "mock-key"),
                grid_player_id=os.getenv("GRID_PLAYER_ID", "mock-player"),
                grid_series_id=os.getenv("GRID_SERIES_ID", "mock-series"),
                data_source="grid",
                max_steps=1,
            )
            if trigger_third_call:
                client = GridClient(api_key="mock-key")
                try:
                    client.run_query(q.Q_SERIES_BY_ID, {"id": "mock-series"})
                except Exception:
                    pass
            if double_run:
                payload = _run_ai_mode(
                    states=[],
                    context_meta={},
                    coach_query=f"Grid resilience {label}-second",
                    anchor_team_id=None,
                    grid_api_key=os.getenv("GRID_API_KEY", "mock-key"),
                    grid_player_id=os.getenv("GRID_PLAYER_ID", "mock-player"),
                    grid_series_id=os.getenv("GRID_SERIES_ID", "mock-series"),
                    data_source="grid",
                    max_steps=1,
                )
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
        finally:
            clear_run_budget()
    _print_case(label, payload, err)


if __name__ == "__main__":
    os.environ.setdefault("DATA_SOURCE", "grid")
    run_case("Case A (429)", fault="429", run_budget=2)
    run_case("Case B (EOF)", fault="EOF", run_budget=2)
    run_case("Case C (RunBudget=2)", fault="NONE", run_budget=2, trigger_third_call=True)
    run_case("Case D (cache)", fault="NONE", run_budget=4, double_run=True)
