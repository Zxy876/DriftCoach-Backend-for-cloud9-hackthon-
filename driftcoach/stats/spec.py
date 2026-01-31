from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional


TimeWindow = Literal["LAST_3_MONTHS"]


@dataclass(frozen=True)
class StatsQuerySpec:
    target: Literal["player", "team"]
    target_id: str
    time_window: Optional[TimeWindow] = None
    tournament_ids: Optional[List[str]] = None

    def is_valid(self) -> bool:
        has_id = self.target_id is not None and str(self.target_id) != ""
        has_tw = self.time_window is not None
        has_tournaments = bool(self.tournament_ids) and len(self.tournament_ids or []) > 0
        return has_id and (has_tw or has_tournaments)
