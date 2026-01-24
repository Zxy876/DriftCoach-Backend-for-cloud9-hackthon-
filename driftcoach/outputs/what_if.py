from dataclasses import dataclass
from typing import Dict, List

from driftcoach.core.action import Action


@dataclass(frozen=True)
class WhatIfOutcome:
    state: str
    actions: List[Action]
    outcomes: Dict[Action, Dict[str, float]]
    confidence: float

    @staticmethod
    def build(state: str, actions: List[Action], outcomes: Dict[Action, Dict[str, float]], confidence: float) -> "WhatIfOutcome":
        if not actions:
            raise ValueError("actions cannot be empty")
        if set(actions) != set(outcomes.keys()):
            raise ValueError("actions and outcomes keys must match")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        for act, payload in outcomes.items():
            win_prob = payload.get("win_prob")
            if win_prob is None or not 0.0 <= win_prob <= 1.0:
                raise ValueError(f"invalid win_prob for action {act}")
        return WhatIfOutcome(state=state, actions=actions, outcomes=outcomes, confidence=confidence)
