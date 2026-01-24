from typing import Sequence

from driftcoach.analysis.registry import AnalysisMethod
from driftcoach.core.derived_fact import DerivedFact
from driftcoach.core.state import State


class EconCascade(AnalysisMethod):
    name = "econ_cascade"
    scope = "team"
    requires = ["round_result"]

    def __init__(self) -> None:
        self.trigger_conditions = {
            "min_samples": lambda states: len(states) >= 20,
        }

    def eligible(self, states: Sequence[State]) -> bool:
        return len(states) >= 20

    def run(self, states: Sequence[State]):
        samples = [s for s in states if s.extras.get("round_result")]
        if not samples:
            return None

        disadvantaged = [s for s in samples if s.econ_diff <= -2000]
        losses_disadvantaged = sum(1 for s in disadvantaged if s.extras.get("round_result") == "LOSS")
        total_disadvantaged = len(disadvantaged)
        cascade_rate = losses_disadvantaged / total_disadvantaged if total_disadvantaged else 0.0

        losses_all = sum(1 for s in samples if s.extras.get("round_result") == "LOSS")
        baseline = losses_all / len(samples) if samples else 0.0

        confidence = min(1.0, total_disadvantaged / 40.0)

        return DerivedFact(
            fact_type="econ_cascade_rate",
            value=cascade_rate,
            baseline=baseline,
            sample_size=total_disadvantaged,
            metadata={
                "losses_disadvantaged": losses_disadvantaged,
                "total_disadvantaged": total_disadvantaged,
                "econ_threshold": -2000,
                "confidence": confidence,
            },
        )
