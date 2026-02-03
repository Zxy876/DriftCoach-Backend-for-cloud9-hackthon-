from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from driftcoach.core.state import State
from driftcoach.core.action import Action


class StateSimilarity:
    def __init__(self, n_components: int = 5, n_neighbors: int = 5) -> None:
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=n_components)
        self.nn = NearestNeighbors(n_neighbors=n_neighbors, metric="cosine")
        self.fitted = False
        self._states: List[State] = []

    def _to_matrix(self, states: Sequence[State]) -> np.ndarray:
        return np.array(
            [
                [
                    s.score_diff,
                    s.econ_diff,
                    s.alive_diff,
                    s.ult_diff,
                ]
                for s in states
            ]
        )

    def fit(self, states: Sequence[State]) -> None:
        matrix = self._to_matrix(states)
        scaled = self.scaler.fit_transform(matrix)
        reduced = self.pca.fit_transform(scaled)
        self.nn.fit(reduced)
        self._states = list(states)
        self.fitted = True

    def query(self, state: State) -> List[Tuple[int, float]]:
        if not self.fitted:
            raise RuntimeError("StateSimilarity not fitted")
        vector = self._to_matrix([state])
        scaled = self.scaler.transform(vector)
        reduced = self.pca.transform(scaled)
        distances, indices = self.nn.kneighbors(reduced)
        return list(zip(indices[0].tolist(), distances[0].tolist()))

    def find_similar_states(self, state: State, action: Action | None = None, k: int = 10) -> List[State]:
        """Return top-k similar states; optionally filter by action stored in extras."""
        neighbors = self.query(state)
        results: List[State] = []
        for idx, _dist in neighbors:
            if idx >= len(self._states):
                continue
            candidate = self._states[idx]
            cand_action = None
            if hasattr(candidate, "extras"):
                cand_action = candidate.extras.get("action") or candidate.extras.get("planned_action")
            if action and cand_action and cand_action != action:
                continue
            results.append(candidate)
            if len(results) >= k:
                break
        return results
