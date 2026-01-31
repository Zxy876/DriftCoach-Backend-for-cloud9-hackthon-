from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_outputs(monkeypatch):
    """Disable heavy output generation (PCA, what-if) in tests to avoid noise.

    This keeps stats convergence tests focused on stats path, not display layers.
    """

    def _noop_generate_outputs(*args, **kwargs):
        return []

    monkeypatch.setattr("driftcoach.api.generate_outputs_from_states", _noop_generate_outputs, raising=False)

    # Also guard against any PCA fit via state_similarity if reached
    try:
        from driftcoach.ml import state_similarity
    except Exception:
        return

    def _safe_fit(self, states):
        return self

    monkeypatch.setattr(state_similarity.StateSimilarity, "fit", _safe_fit, raising=False)
    monkeypatch.setattr(state_similarity.StateSimilarity, "transform", lambda self, x: x, raising=False)
