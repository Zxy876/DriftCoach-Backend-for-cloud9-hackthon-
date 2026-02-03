from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from driftcoach.core.action import Action
from driftcoach.core.state import State
from driftcoach.ml.outcome_model import OutcomeModel


@dataclass(frozen=True)
class WhatIfOutcome:
    state: State | str
    actions: List[Action]
    outcomes: Dict[Action, Dict[str, float | int | bool | None]]
    confidence: float

    @staticmethod
    def build(state: State | str, actions: List[Action], outcomes: Dict[Action, Dict[str, float | int | bool | None]], confidence: float) -> "WhatIfOutcome":
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
            support = payload.get("support") or payload.get("support_count")
            if support is not None and support < 0:
                raise ValueError(f"invalid support for action {act}")
        return WhatIfOutcome(state=state, actions=actions, outcomes=outcomes, confidence=confidence)


def _safe_predict(model: OutcomeModel, state: State, action: Action) -> float:
    try:
        return float(model.predict_prob(state, action))
    except Exception:
        return 0.5


def generate_what_if_analysis(
    current_state: State,
    alternative_actions: Sequence[Action],
    model: OutcomeModel,
    similarity_finder: Any,
    top_k_similar: int = 10,
) -> WhatIfOutcome:
    outcomes: Dict[Action, Dict[str, float | int | bool | None]] = {}
    confidences: List[float] = []

    actions = list(alternative_actions) or [Action.CONTEST, Action.SAVE]

    for action in actions:
        win_prob = _safe_predict(model, current_state, action)

        similar_states = []
        if similarity_finder:
            try:
                similar_states = similarity_finder.find_similar_states(current_state, action, k=top_k_similar)
            except Exception:
                similar_states = []

        actual_wins = 0
        for s in similar_states:
            outcome = None
            if hasattr(s, "extras"):
                outcome = s.extras.get("round_result") or s.extras.get("outcome")
                if s.extras.get("action") and s.extras.get("action") != action:
                    continue
            if outcome in {"WIN", 1, True}:
                actual_wins += 1
            elif outcome in {"LOSS", 0, False}:
                actual_wins += 0

        support_count = len(similar_states)
        support_rate = (actual_wins / support_count) if support_count else 0.0
        insuff = support_count < 5

        outcomes[action] = {
            "win_prob": win_prob,
            "support_rate": support_rate,
            "support_count": support_count,
            "insufficient_support": insuff,
        }
        confidences.append(win_prob)

    if len(confidences) > 1:
        overall_confidence = max(confidences) - min(confidences)
    else:
        overall_confidence = 0.5

    return WhatIfOutcome.build(
        state=current_state,
        actions=actions,
        outcomes=outcomes,
        confidence=min(1.0, max(0.0, overall_confidence)),
    )
