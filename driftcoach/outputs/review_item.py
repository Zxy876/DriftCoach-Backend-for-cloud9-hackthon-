from dataclasses import dataclass
from typing import List

from driftcoach.core.derived_fact import DerivedFact


@dataclass(frozen=True)
class ReviewAgendaItem:
    match_id: str
    topic: str
    states_involved: List[str]
    evidence: List[DerivedFact]
