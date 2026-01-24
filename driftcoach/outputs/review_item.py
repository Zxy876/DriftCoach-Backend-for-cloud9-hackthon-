from dataclasses import dataclass
from typing import List

from driftcoach.core.derived_fact import DerivedFact


@dataclass(frozen=True)
class ReviewAgendaItem:
    match_id: str
    topic: str
    states_involved: List[str]
    evidence: List[DerivedFact]
    confidence: float

    @staticmethod
    def build(match_id: str, topic: str, states_involved: List[str], evidence: List[DerivedFact], confidence: float) -> "ReviewAgendaItem":
        if not states_involved:
            raise ValueError("states_involved cannot be empty")
        if not evidence:
            raise ValueError("evidence cannot be empty")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return ReviewAgendaItem(
            match_id=match_id,
            topic=topic,
            states_involved=states_involved,
            evidence=evidence,
            confidence=confidence,
        )
