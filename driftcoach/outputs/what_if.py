from dataclasses import dataclass
from typing import Dict, List

from driftcoach.core.action import Action


@dataclass(frozen=True)
class WhatIfOutcome:
    state: str
    actions: List[Action]
    outcomes: Dict[Action, Dict[str, float | int | bool | None]]
    confidence: float

    @staticmethod
    def build(state: str, actions: List[Action], outcomes: Dict[Action, Dict[str, float | int | bool | None]], confidence: float) -> "WhatIfOutcome":
        if not actions:
            raise ValueError("actions cannot be empty")
        if set(actions) != set(outcomes.keys()):
            raise ValueError("actions and outcomes keys must match")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        for act, payload in outcomes.items():
            win_prob = payload.get("win_prob")
            insufficient = payload.get("insufficient_support", False)
            if win_prob is None:
                if not insufficient:
                    raise ValueError(f"missing win_prob for action {act}")
            else:
                if not 0.0 <= float(win_prob) <= 1.0:
                    raise ValueError(f"invalid win_prob for action {act}")
            support = payload.get("support")
            if support is not None and support < 0:
                raise ValueError(f"invalid support for action {act}")
        return WhatIfOutcome(state=state, actions=actions, outcomes=outcomes, confidence=confidence)
