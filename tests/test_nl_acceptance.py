from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Any

import pytest
import requests

from driftcoach.api import _run_ai_mode
from driftcoach.adapters.grid import queries as q
from driftcoach.adapters.grid.client import clear_response_cache
from driftcoach.adapters.grid.rate_budget import set_run_budget, clear_run_budget, reset_grid_controls


NL_INPUTS = [
    "这名选手最近的发挥稳不稳定？",
    "你觉得他最近是不是有点异常？",
    "他最近的状态和以前比怎么样？",
]


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")
        return None


def _mock_stats_payload(target: str = "player") -> Dict[str, Any]:
    node_key = "playerStatistics" if target in {"PLAYER_STATS", "player"} else "teamStatistics"
    return {
        "data": {
            node_key: {
                "aggregationSeriesIds": ["mock-series-agg"],
                "series": {"count": 6, "kills": {"sum": 60, "min": 8, "max": 12, "avg": 10.0}},
                "game": {"count": 12, "wins": {"value": 8, "count": 8, "percentage": 0.666, "streak": {"min": 1, "max": 3, "current": 2}}},
                "segment": {"type": "map", "count": 12, "deaths": {"sum": 90, "min": 5, "max": 10, "avg": 7.5}},
                "trend": {"winRate": {"slope": 0.02}},
            }
        }
    }


@contextmanager
def stub_requests(stats_ok: bool = True):
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

        if "playerStatistics" in query:
            return _FakeResponse(_mock_stats_payload("player") if stats_ok else {"data": {"playerStatistics": None}})
        if "teamStatistics" in query:
            return _FakeResponse(_mock_stats_payload("team") if stats_ok else {"data": {"teamStatistics": None}})

        return _FakeResponse({"data": {}})

    requests.post = _fake_post
    try:
        yield
    finally:
        requests.post = original_post


def _run_query(coach_query: str, max_steps: int = 2) -> Dict[str, Any]:
    payload = _run_ai_mode(
        states=[],
        context_meta={},
        coach_query=coach_query,
        anchor_team_id=None,
        grid_api_key=os.getenv("GRID_API_KEY", "mock-key"),
        grid_player_id=os.getenv("GRID_PLAYER_ID", "91"),
        grid_series_id=os.getenv("GRID_SERIES_ID", "2819676"),
        data_source="grid",
        max_steps=max_steps,
    )
    return payload


def _save(label: str, payload: Dict[str, Any]) -> None:
    try:
        with open(f"/tmp/{label}.json", "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _reset_env():
    os.environ.setdefault("DATA_SOURCE", "grid")
    os.environ.setdefault("GRID_FAULT_MODE", "NONE")
    reset_grid_controls()
    clear_response_cache()
    yield
    clear_run_budget()


def _assert_research_plan(payload: Dict[str, Any]):
    rp = payload.get("ai", {}).get("research_plan", {})
    assert rp.get("research_intent") == "PERFORMANCE_STABILITY"
    axes = rp.get("evidence_axes") or []
    assert any(ax.get("axis") == "baseline" and ax.get("required") for ax in axes)
    targets = rp.get("convergence_targets") or []
    assert targets and targets[0].get("name") in {"PLAYER_STATS", "player"}


def _assert_answer_success(payload: Dict[str, Any]):
    ans = (payload.get("ai", {}).get("answer") or "")
    assert ("稳定" in ans) or ("异常" in ans) or ("波动" in ans)
    assert "系统限制" not in ans and "接口不可用" not in ans and "不构成结论" not in ans


def _assert_answer_blocked(payload: Dict[str, Any]):
    ans = (payload.get("ai", {}).get("answer") or "")
    assert "方向性" in ans or "判断" in ans
    assert "高置信" in ans or "置信度" in ans
    assert "基线" in ans or "历史" in ans


def test_nl_success_cases():
    set_run_budget(5)
    with stub_requests(stats_ok=True):
        for idx, qtext in enumerate(NL_INPUTS, start=1):
            payload = _run_query(qtext, max_steps=2)
            _save(f"nl_case_{idx}_success", {
                "input_query": qtext,
                "ai": payload.get("ai", {}),
                "research_plan": payload.get("ai", {}).get("research_plan"),
                "research_progress": payload.get("ai", {}).get("research_progress"),
                "stats_results": payload.get("ai", {}).get("stats_results"),
                "grid_health": payload.get("ai", {}).get("grid_health") or payload.get("context", {}).get("grid_health"),
            })
            _assert_research_plan(payload)
            stats_results = payload.get("ai", {}).get("stats_results") or []
            assert stats_results and stats_results[0].get("status") == "success"
            rp = payload.get("ai", {}).get("research_progress") or {}
            assert rp.get("can_answer") is True
            assert "baseline" not in (rp.get("missing_axes") or [])
            _assert_answer_success(payload)


def test_nl_blocked_cases():
    set_run_budget(0)
    os.environ["GRID_FAULT_MODE"] = "429"
    with stub_requests(stats_ok=True):
        for idx, qtext in enumerate(NL_INPUTS, start=1):
            payload = _run_query(qtext, max_steps=1)
            _save(f"nl_case_{idx}_blocked", {
                "input_query": qtext,
                "ai": payload.get("ai", {}),
                "research_plan": payload.get("ai", {}).get("research_plan"),
                "research_progress": payload.get("ai", {}).get("research_progress"),
                "stats_results": payload.get("ai", {}).get("stats_results"),
                "grid_health": payload.get("ai", {}).get("grid_health") or payload.get("context", {}).get("grid_health"),
            })
            _assert_research_plan(payload)
            stats_results = payload.get("ai", {}).get("stats_results") or []
            assert stats_results and stats_results[0].get("status") == "skipped"
            assert stats_results[0].get("reason") in {"grid_budget_exhausted", "circuit_open"}
            rp = payload.get("ai", {}).get("research_progress") or {}
            assert rp.get("can_answer") is False
            _assert_answer_blocked(payload)


if __name__ == "__main__":
    import pytest as _pytest

    _pytest.main([__file__])
