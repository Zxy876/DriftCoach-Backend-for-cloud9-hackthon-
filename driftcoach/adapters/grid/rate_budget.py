from __future__ import annotations

import threading
import time
import contextvars
from typing import Optional, Dict


class GridRateExceeded(RuntimeError):
    pass


class GridRunBudgetExceeded(RuntimeError):
    pass


class GridCircuitOpen(RuntimeError):
    pass


_debug_counters_lock = threading.Lock()
_debug_counters: Dict[str, int] = {
    "calls_attempted": 0,
    "calls_sent": 0,
    "cache_hit": 0,
    "cache_miss": 0,
    "rate_budget_denied": 0,
    "run_budget_denied": 0,
    "circuit_open_denied": 0,
}


def _inc_counter(key: str, value: int = 1) -> None:
    with _debug_counters_lock:
        _debug_counters[key] = _debug_counters.get(key, 0) + value


def reset_debug_counters() -> None:
    with _debug_counters_lock:
        for k in _debug_counters.keys():
            _debug_counters[k] = 0


def get_debug_counters() -> Dict[str, int]:
    with _debug_counters_lock:
        return dict(_debug_counters)


def reset_grid_controls() -> None:
    """Reset rate budget, circuit breaker, run budget, and counters (test helper)."""
    global global_rate_budget, global_circuit
    global_rate_budget = RateBudget()
    global_circuit = CircuitBreaker()
    clear_run_budget()
    reset_debug_counters()


def mark_call_attempted() -> None:
    _inc_counter("calls_attempted")


def mark_call_sent() -> None:
    _inc_counter("calls_sent")


def mark_cache_hit() -> None:
    _inc_counter("cache_hit")


def mark_cache_miss() -> None:
    _inc_counter("cache_miss")


class RateBudget:
    """Process-wide rate limiter (no sleep; raises on exhaustion)."""

    def __init__(self, max_requests: int = 15, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.remaining = max_requests
        self.reset_at = time.time() + window_seconds
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.time()
            if now >= self.reset_at:
                self.remaining = self.max_requests
                self.reset_at = now + self.window_seconds
            if self.remaining <= 0:
                _inc_counter("rate_budget_denied")
                raise GridRateExceeded("grid_global_budget_exhausted")
            self.remaining -= 1


class RunBudget:
    """Per-run limiter (e.g., _run_ai_mode scoped)."""

    def __init__(self, max_requests: int) -> None:
        self.max_requests = max_requests
        self.used = 0

    def acquire(self) -> None:
        if self.used >= self.max_requests:
            _inc_counter("run_budget_denied")
            raise GridRunBudgetExceeded("grid_run_budget_exhausted")
        self.used += 1


class CircuitBreaker:
    def __init__(self, open_seconds: float = 600.0) -> None:
        self.state = "CLOSED"
        self.open_until = 0.0
        self.consecutive_429 = 0
        self.open_seconds = open_seconds
        self.last_reason: Optional[str] = None
        self._lock = threading.Lock()

    def check(self) -> None:
        with self._lock:
            if self.state == "OPEN" and time.time() < self.open_until:
                _inc_counter("circuit_open_denied")
                raise GridCircuitOpen(self.last_reason or "grid_circuit_open")
            if self.state == "OPEN" and time.time() >= self.open_until:
                # allow traffic again
                self.state = "CLOSED"
                self.consecutive_429 = 0
                self.last_reason = None

    def record_success(self) -> None:
        with self._lock:
            self.consecutive_429 = 0
            if self.state != "OPEN":
                self.last_reason = None

    def record_failure(self, status: Optional[int], exc: Exception) -> None:
        reason = None
        if status == 429:
            self.consecutive_429 += 1
            reason = "rate_limit"
        else:
            self.consecutive_429 = 0
        text = str(exc).lower()
        is_eof = "eof" in text or "handshake" in text
        should_open = False
        if self.consecutive_429 >= 3:
            should_open = True
            reason = reason or "rate_limit"
        if is_eof:
            should_open = True
            reason = reason or "ssl_eof"
        if should_open:
            with self._lock:
                self.state = "OPEN"
                self.open_until = time.time() + self.open_seconds
                self.last_reason = reason or "grid_circuit_open"


# Global, process-wide budget and circuit
global_rate_budget: Optional[RateBudget] = RateBudget()
global_circuit: Optional[CircuitBreaker] = CircuitBreaker()

_run_budget_var: contextvars.ContextVar[Optional[RunBudget]] = contextvars.ContextVar("grid_run_budget", default=None)


def set_run_budget(limit: int) -> None:
    _run_budget_var.set(RunBudget(limit))


def clear_run_budget() -> None:
    _run_budget_var.set(None)


def get_run_budget() -> Optional[RunBudget]:
    return _run_budget_var.get()


def get_rate_budget() -> RateBudget:
    global global_rate_budget
    if global_rate_budget is None:
        global_rate_budget = RateBudget()
    return global_rate_budget


def get_circuit() -> CircuitBreaker:
    global global_circuit
    if global_circuit is None:
        global_circuit = CircuitBreaker()
    return global_circuit


def grid_health_snapshot() -> dict:
    cb = get_circuit()
    rb = get_rate_budget()
    counters = get_debug_counters()
    return {
        "circuit_state": cb.state,
        "circuit_open_until": cb.open_until,
        "circuit_reason": cb.last_reason,
        "global_remaining": rb.remaining,
        "global_reset_at": rb.reset_at,
        "run_budget_remaining": (get_run_budget().max_requests - get_run_budget().used) if get_run_budget() else None,
        "debug_counters": counters,
    }
