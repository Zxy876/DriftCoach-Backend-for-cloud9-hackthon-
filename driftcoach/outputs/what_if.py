from dataclasses import dataclass
from typing import Dict, List

from driftcoach.core.action import Action


@dataclass(frozen=True)
class WhatIfOutcome:
    state: str
    actions: List[Action]
    outcomes: Dict[Action, Dict[str, float]]
    confidence: float
