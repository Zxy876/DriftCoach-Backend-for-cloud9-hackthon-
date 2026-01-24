from dataclasses import dataclass
from typing import List

from driftcoach.core.derived_fact import DerivedFact


@dataclass(frozen=True)
class Insight:
    subject: str
    claim: str
    derived_facts: List[DerivedFact]
    confidence: float
    failure_conditions: List[str]
