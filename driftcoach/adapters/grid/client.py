import os
import logging
import time
import json
import hashlib
from typing import Dict, Any, Tuple

import requests

from driftcoach.adapters.grid.rate_budget import (
    get_rate_budget,
    get_run_budget,
    get_circuit,
    GridRateExceeded,
    GridRunBudgetExceeded,
    GridCircuitOpen,
    mark_call_attempted,
    mark_call_sent,
    mark_cache_hit,
    mark_cache_miss,
)

GRID_ENDPOINT = os.getenv("GRID_GRAPHQL_URL", "https://api-op.grid.gg/central-data/graphql")
logger = logging.getLogger(__name__)


class _CacheEntry:
    def __init__(self, value: Dict[str, Any], expires_at: float) -> None:
        self.value = value
        self.expires_at = expires_at


class _ResponseCache:
    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self.ttl_seconds = ttl_seconds
        self.data: Dict[str, _CacheEntry] = {}
        self.error_cache: Dict[str, str] = {}

    def _key(self, query: str, variables: Dict[str, Any]) -> str:
        key_payload = json.dumps({"q": query, "v": variables}, sort_keys=True, default=str)
        return hashlib.sha1(key_payload.encode("utf-8")).hexdigest()

    def get(self, query: str, variables: Dict[str, Any]) -> Tuple[Dict[str, Any] | None, str | None]:
        key = self._key(query, variables)
        if key in self.error_cache:
            return None, self.error_cache[key]
        entry = self.data.get(key)
        if entry and time.time() < entry.expires_at:
            return entry.value, None
        if entry:
            self.data.pop(key, None)
        return None, None

    def set(self, query: str, variables: Dict[str, Any], value: Dict[str, Any], ttl_override: float | None = None) -> None:
        key = self._key(query, variables)
        ttl = ttl_override if ttl_override is not None else self.ttl_seconds
        self.data[key] = _CacheEntry(value=value, expires_at=time.time() + ttl)

    def set_error(self, query: str, variables: Dict[str, Any], reason: str) -> None:
        key = self._key(query, variables)
        self.error_cache[key] = reason

    def clear(self) -> None:
        self.data.clear()
        self.error_cache.clear()


_response_cache = _ResponseCache()


def clear_response_cache() -> None:
    _response_cache.clear()


class GridClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def run_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Pure IO: run GraphQL query with global/run budgets and circuit breaker. No retry."""
        circuit = get_circuit()
        budget = get_rate_budget()
        run_budget = get_run_budget()

        mark_call_attempted()

        circuit.check()
        if run_budget:
            run_budget.acquire()
        budget.acquire()

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        body = {"query": query, "variables": variables}

        cached, cached_err = _response_cache.get(query, variables)
        if cached_err:
            mark_cache_hit()
            raise RuntimeError(cached_err)
        if cached:
            mark_cache_hit()
            return cached
        mark_cache_miss()

        fault_mode = (os.getenv("GRID_FAULT_MODE") or "NONE").upper()
        if fault_mode == "429":
            circuit.record_failure(429, RuntimeError("grid_fault_429"))
            raise GridRateExceeded("grid_fault_429")
        if fault_mode == "EOF":
            circuit.record_failure(None, RuntimeError("grid_fault_eof"))
            raise GridCircuitOpen("grid_fault_eof")

        try:
            mark_call_sent()
            resp = requests.post(
                GRID_ENDPOINT,
                json=body,
                headers=headers,
                timeout=30,
            )
            logger.debug(
                "GRID request",
                extra={
                    "endpoint": GRID_ENDPOINT,
                    "status_code": resp.status_code,
                    "body_preview": resp.text[:200],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("errors"):
                err_str = str(data.get("errors"))
                if "ENHANCE_YOUR_CALM" in err_str or "rate limit" in err_str.lower():
                    circuit.record_failure(resp.status_code, RuntimeError("rate_limit"))
                    raise GridRateExceeded("grid_rate_limit")
                _response_cache.set_error(query, variables, f"schema_error:{err_str}")
                raise RuntimeError(f"GRID GraphQL errors: {data.get('errors')}")
            _response_cache.set(query, variables, data)
            circuit.record_success()
            return data
        except GridRateExceeded:
            raise
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as exc:
            circuit.record_failure(None, exc)
            raise GridCircuitOpen("grid_ssl_or_eof")
        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status == 429:
                circuit.record_failure(status, exc)
                raise GridRateExceeded("grid_rate_limit")
            circuit.record_failure(status, exc)
            raise
        except Exception as exc:
            circuit.record_failure(None, exc)
            raise
