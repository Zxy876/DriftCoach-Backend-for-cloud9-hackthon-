from __future__ import annotations

from typing import Callable, Dict, List, Sequence

from driftcoach.core.state import State


class AnalysisMethod:
    name: str
    scope: str
    requires: List[str]
    trigger_conditions: Dict[str, Callable[[Sequence[State]], bool]]

    def eligible(self, states: Sequence[State]) -> bool:
        raise NotImplementedError

    def run(self, states: Sequence[State]):
        raise NotImplementedError


class AnalysisRegistry:
    def __init__(self) -> None:
        self._methods: Dict[str, AnalysisMethod] = {}

    def register(self, method: AnalysisMethod) -> None:
        if method.name in self._methods:
            raise ValueError(f"Method already registered: {method.name}")
        self._methods[method.name] = method

    def get(self, name: str) -> AnalysisMethod:
        return self._methods[name]

    def all(self) -> List[AnalysisMethod]:
        return list(self._methods.values())
