from dataclasses import dataclass
from typing import Literal

from .action import Action


@dataclass(frozen=True)
class Transition:
    from_state: str
    action: Action
    outcome: Literal["WIN", "LOSS", "UNKNOWN"]
