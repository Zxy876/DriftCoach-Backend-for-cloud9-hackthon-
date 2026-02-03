from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any


class NarrativeType(str, Enum):
    PLAYER_INSIGHT_REPORT = "PLAYER_INSIGHT_REPORT"
    MATCH_REVIEW_AGENDA = "MATCH_REVIEW_AGENDA"
    SUMMARY_REPORT = "SUMMARY_REPORT"
    WHAT_IF_REPORT = "WHAT_IF_REPORT"


@dataclass
class NarrativeInput:
    narrative_type: NarrativeType
    facts: List[Dict[str, Any]]
    scope: Dict[str, Any]


@dataclass
class NarrativeResult:
    narrative_type: NarrativeType
    content: str
    confidence: float
    used_facts: int
