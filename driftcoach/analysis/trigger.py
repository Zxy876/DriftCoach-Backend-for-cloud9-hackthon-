from typing import Sequence

from driftcoach.core.state import State
from .registry import AnalysisMethod


def is_eligible(method: AnalysisMethod, states: Sequence[State]) -> bool:
    if not states:
        return False
    # Check required fields presence in extras
    if getattr(method, "requires", None):
        for req in method.requires:
            def _has(s: State) -> bool:
                if req in (s.extras or {}):
                    return True
                if hasattr(s, req):
                    return getattr(s, req) is not None
                return False

            if not all(_has(s) for s in states):
                return False
    if hasattr(method, "trigger_conditions"):
        for check in method.trigger_conditions.values():
            if not check(states):
                return False
    return method.eligible(states)
