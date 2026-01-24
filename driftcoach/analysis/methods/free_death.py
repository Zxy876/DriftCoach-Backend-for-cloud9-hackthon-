from typing import Sequence

from driftcoach.analysis.registry import AnalysisMethod
from driftcoach.core.derived_fact import DerivedFact
from driftcoach.core.state import State


class FreeDeathImpact(AnalysisMethod):
    name = "free_death_impact"
    scope = "player"
    requires = ["free_death", "round_result"]

    def __init__(self) -> None:
        self.trigger_conditions = {
            "min_samples": lambda states: len(states) >= 30,
        }

    def eligible(self, states: Sequence[State]) -> bool:
        return len(states) >= 30

    def run(self, states: Sequence[State]):
        samples = [s for s in states if s.extras.get("free_death") is not None]
        if not samples:
            return None

        condition_states = [s for s in samples if bool(s.extras.get("free_death"))]
        wins_with_condition = sum(1 for s in condition_states if s.extras.get("round_result") == "WIN")
        total_condition = len(condition_states)
        cond_winrate = wins_with_condition / total_condition if total_condition else 0.0

        wins_all = sum(1 for s in samples if s.extras.get("round_result") == "WIN")
        baseline = wins_all / len(samples) if samples else 0.0

        confidence = min(1.0, total_condition / 50.0)

        return DerivedFact(
            fact_type="conditional_winrate",
            value=cond_winrate,
            baseline=baseline,
            sample_size=total_condition,
            metadata={
                "condition": "free_death",
                "wins_with_condition": wins_with_condition,
                "total_condition": total_condition,
                "confidence": confidence,
            },
        )
