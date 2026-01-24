from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class State:
    state_id: str
    series_id: str
    game_index: int
    timestamp: float
    map: str
    score_diff: int
    econ_diff: int
    alive_diff: int
    ult_diff: int
    objective_context: Optional[str]
    phase: str
    extras: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "State":
        return State(
            state_id=data["state_id"],
            series_id=data.get("series_id", ""),
            game_index=int(data.get("game_index", 0)),
            timestamp=float(data.get("timestamp", 0.0)),
            map=data.get("map", ""),
            score_diff=int(data.get("score_diff", 0)),
            econ_diff=int(data.get("econ_diff", 0)),
            alive_diff=int(data.get("alive_diff", 0)),
            ult_diff=int(data.get("ult_diff", 0)),
            objective_context=data.get("objective_context"),
            phase=data.get("phase", "UNKNOWN"),
            extras=data.get("extras", {}),
        )
