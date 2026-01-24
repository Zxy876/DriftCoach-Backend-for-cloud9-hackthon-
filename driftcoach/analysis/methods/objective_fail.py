from typing import Sequence

from driftcoach.analysis.registry import AnalysisMethod
from driftcoach.core.derived_fact import DerivedFact
from driftcoach.core.state import State


class ObjectiveFail(AnalysisMethod):
    name = "objective_fail"
    scope = "team"
    requires = ["round_result", "contest_attempt"]

    def __init__(self) -> None:
        self.trigger_conditions = {
            "min_samples": lambda states: len(states) >= 15,
        }

    def eligible(self, states: Sequence[State]) -> bool:
        return len(states) >= 15

    def run(self, states: Sequence[State]):
        samples = [s for s in states if s.objective_context]
        if not samples:
            return None

        contests = [s for s in samples if s.extras.get("contest_attempt")]
        failures = sum(1 for s in contests if s.extras.get("round_result") == "LOSS")
        total_contests = len(contests)
        fail_rate = failures / total_contests if total_contests else 0.0

        losses_all = sum(1 for s in samples if s.extras.get("round_result") == "LOSS")
        baseline = losses_all / len(samples) if samples else 0.0

        confidence = min(1.0, total_contests / 30.0)

        return DerivedFact(
            fact_type="objective_fail_rate",
            value=fail_rate,
            baseline=baseline,
            sample_size=total_contests,
            metadata={
                "objective": "generic",
                "failures": failures,
                "total_contests": total_contests,
                "confidence": confidence,
            },
        )
