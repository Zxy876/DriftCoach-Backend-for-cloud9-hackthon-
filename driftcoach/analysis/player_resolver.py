from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from driftcoach.adapters.grid.file_download_client import RawEvent


def _normalize(s: Optional[str]) -> Optional[str]:
    return s.lower().strip() if isinstance(s, str) else None


def _collect_players_from_series_state(series_state: Dict[str, Any]) -> List[Tuple[str, str]]:
    players: List[Tuple[str, str]] = []
    for team in (series_state.get("teams") or []):
        for p in team.get("players") or []:
            pid = p.get("id")
            name = p.get("name")
            if pid and name:
                players.append((str(pid), str(name)))
    return players


def _collect_players_from_events(events: List[RawEvent]) -> List[Tuple[str, str]]:
    seen: List[Tuple[str, str]] = []
    for ev in events:
        payload = ev.payload or {}
        for key in ["actor", "target", "player", "victim", "killer", "killed"]:
            obj = payload.get(key)
            if isinstance(obj, dict):
                pid = obj.get("id") or obj.get("playerId")
                name = obj.get("name")
                if pid and name:
                    seen.append((str(pid), str(name)))
            elif obj:
                # sometimes name appears without id
                seen.append((None, str(obj)))
    return seen


def resolve_player_id(series_events: List[RawEvent], player_name: Optional[str], series_state: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], Optional[str]]:
    """Resolve player_id within a single series using events/state only.

    Returns (player_id, reason). Reason is None when resolved.
    player_id 是执行细节，player_name 才是认知入口。
    """
    if not player_name:
        return None, "missing_player_name"

    target = _normalize(player_name)
    candidates: List[Tuple[Optional[str], str]] = []

    for pid, name in _collect_players_from_series_state(series_state or {}):
        if _normalize(name) == target:
            candidates.append((pid, name))

    for pid, name in _collect_players_from_events(series_events or []):
        if _normalize(name) == target:
            candidates.append((pid, name))

    # Deduplicate by id/name pair
    dedup: Dict[Tuple[Optional[str], str], None] = {}
    for pid, name in candidates:
        dedup[(pid, name)] = None
    unique = list(dedup.keys())

    if not unique:
        return None, "player_not_found"
    # prefer candidates with id present
    with_id = [pid for pid, _ in unique if pid]
    if len(with_id) == 1:
        return with_id[0], None
    if len(with_id) > 1:
        # conflicting ids for same name
        return None, "player_ambiguous"
    # only names without ids
    if len(unique) == 1:
        return None, "player_missing_id"
    return None, "player_ambiguous"
