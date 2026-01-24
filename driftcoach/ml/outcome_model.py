from typing import Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression

from driftcoach.core.state import State
from driftcoach.core.action import Action


class OutcomeModel:
    def __init__(self) -> None:
        self.model = LogisticRegression(max_iter=500)
        self.fitted = False

    def _to_matrix(self, states: Sequence[State], actions: Sequence[Action]) -> np.ndarray:
        return np.array(
            [
                [
                    s.score_diff,
                    s.econ_diff,
                    s.alive_diff,
                    s.ult_diff,
                    1 if a in (Action.RETAKE, Action.FORCE, Action.CONTEST) else 0,
                ]
                for s, a in zip(states, actions)
            ]
        )

    def fit(self, states: Sequence[State], actions: Sequence[Action], outcomes: Sequence[int]) -> None:
        matrix = self._to_matrix(states, actions)
        y = np.array(outcomes)
        self.model.fit(matrix, y)
        self.fitted = True

    def predict_prob(self, state: State, action: Action) -> float:
        if not self.fitted:
            raise RuntimeError("OutcomeModel not fitted")
        matrix = self._to_matrix([state], [action])
        return float(self.model.predict_proba(matrix)[0][1])
