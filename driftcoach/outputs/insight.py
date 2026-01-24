from dataclasses import dataclass
from typing import List

from driftcoach.core.derived_fact import DerivedFact


def _check_confidence(value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class Insight:
    subject: str
    claim: str
    derived_facts: List[DerivedFact]
    confidence: float
    failure_conditions: List[str]

    @staticmethod
    def build(subject: str, claim: str, derived_facts: List[DerivedFact], confidence: float, failure_conditions: List[str]) -> "Insight":
        _check_confidence(confidence)
        if not derived_facts:
            raise ValueError("derived_facts cannot be empty")
        return Insight(
            subject=subject,
            claim=claim,
            derived_facts=derived_facts,
            confidence=confidence,
            failure_conditions=failure_conditions,
        )
