"""
Experimental File Download API client for event-level data.

Constraints:
- Series_id is the only entry; optional api_key uses GRID_API_KEY env.
- Best-effort fetch + parse; returns empty with reason on failure.
"""

from __future__ import annotations

import gzip
import json
import os
import pathlib
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


@dataclass
class RawEvent:
    kind: str
    payload: Dict[str, Any]
    timestamp: Any | None
    round: int | None
    event_type: str | None
    actor: str | None
    target: str | None


@dataclass
class EventLoadResult:
    events: List[RawEvent]
    meta: Dict[str, Any]


LIST_ENDPOINTS = [
    "https://api.grid.gg/file-download/list/{series_id}",
    "https://api-op.grid.gg/file-download/list/{series_id}",
]


def _classify_event(payload: Dict[str, Any]) -> str:
    etype = (payload.get("type") or payload.get("eventType") or payload.get("action") or "").lower()
    name = (payload.get("name") or "").lower()
    if ("round" in etype and ("end" in etype or "won" in etype)) or etype.endswith("ended-round"):
        return "ROUND_END"
    if "kill" in etype or "death" in etype or "damage" in etype or "kill" in name or "death" in name:
        return "KILL_DEATH"
    if "economy" in etype or "money" in etype or "econ" in name:
        return "ECONOMY_SNAPSHOT"
    if "objective" in etype or "bomb" in etype or "spike" in etype or "plant" in etype or "defuse" in etype:
        return "OBJECTIVE"
    return "UNKNOWN"


def _normalize_event(payload: Dict[str, Any]) -> RawEvent:
    kind = _classify_event(payload)
    ts = payload.get("timestamp") or payload.get("time") or payload.get("ts")
    rnd = payload.get("round") or payload.get("roundNumber") or payload.get("round_num")
    etype = payload.get("type") or payload.get("eventType") or payload.get("name")
    actor_raw = payload.get("actor")
    if isinstance(actor_raw, dict):
        actor = actor_raw.get("id") or actor_raw.get("name")
    else:
        actor = actor_raw or payload.get("killer") or payload.get("player") or payload.get("playerId")
    target_raw = payload.get("target") or payload.get("victim") or payload.get("killed")
    if isinstance(target_raw, dict):
        target = target_raw.get("id") or target_raw.get("name")
    else:
        target = target_raw
    return RawEvent(kind=kind, payload=payload, timestamp=ts, round=rnd, event_type=etype, actor=actor, target=target)


def _read_json_bytes(data: bytes) -> Any:
    text = data.decode("utf-8", errors="ignore")
    try:
        return json.loads(text)
    except Exception:
        # try json lines
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        objs = []
        for ln in lines:
            try:
                objs.append(json.loads(ln))
            except Exception:
                continue
        if objs:
            return objs
    return None


def _extract_events_from_file(path: pathlib.Path) -> Tuple[List[RawEvent], Dict[str, Any]]:
    events: List[RawEvent] = []
    meta: Dict[str, Any] = {"file_size": path.stat().st_size}

    def _append(obj: Any) -> None:
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    inner = item.get("events")
                    if isinstance(inner, list):
                        for ev in inner:
                            if isinstance(ev, dict):
                                events.append(_normalize_event(ev))
                    events.append(_normalize_event(item))
        elif isinstance(obj, dict):
            inner = obj.get("events")
            if isinstance(inner, list) and inner:
                for ev in inner:
                    if isinstance(ev, dict):
                        events.append(_normalize_event(ev))
            events.append(_normalize_event(obj))

    if zipfile.is_zipfile(path):
        try:
            with zipfile.ZipFile(path, "r") as zf:
                for name in zf.namelist():
                    try:
                        with zf.open(name) as f:
                            data = f.read()
                            obj = _read_json_bytes(data)
                            if obj is not None:
                                _append(obj)
                    except Exception:
                        continue
        except zipfile.BadZipFile:
            obj = _read_json_bytes(path.read_bytes())
            if obj is not None:
                _append(obj)
    elif path.suffix == ".gz":
        with gzip.open(path, "rb") as f:
            obj = _read_json_bytes(f.read())
            if obj is not None:
                _append(obj)
    else:
        with path.open("rb") as f:
            obj = _read_json_bytes(f.read())
            if obj is not None:
                _append(obj)

    meta["event_count"] = len(events)
    return events, meta


def _pick_file(entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not entries:
        return None
    entries_sorted = sorted(
        entries,
        key=lambda e: 0 if "event" in (e.get("fileName") or e.get("name") or "").lower() else 1,
    )
    return entries_sorted[0]


def _normalize_descriptor(entry: Dict[str, Any]) -> Dict[str, Any]:
    file_name = entry.get("fileName") or entry.get("name")
    url = entry.get("downloadUrl") or entry.get("url") or entry.get("href") or entry.get("fullURL")
    file_type = None
    if file_name:
        file_type = pathlib.Path(file_name).suffix.lstrip(".") or None
    return {
        "file_name": file_name,
        "file_url": url,
        "file_type": file_type,
        "map": entry.get("map") or entry.get("mapName"),
        "game_index": entry.get("game") or entry.get("gameIndex") or entry.get("game_number"),
        "chunk": entry.get("chunk") or entry.get("part"),
        "source": "file_download",
        "raw": entry,
    }


def _list_files(api_key: str, series_id: str) -> Tuple[List[Dict[str, Any]], str | None]:
    headers = {"x-api-key": api_key, "accept": "application/json"}
    session = requests.Session()
    errors: List[str] = []
    for tmpl in LIST_ENDPOINTS:
        url = tmpl.format(series_id=series_id)
        try:
            resp = session.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    entries: List[Dict[str, Any]] = []
                    if isinstance(data, dict) and data.get("files"):
                        entries = data.get("files", [])
                    elif isinstance(data, list):
                        entries = data
                    if entries:
                        return [_normalize_descriptor(e) for e in entries], url
                    errors.append(f"invalid_json:{url}:{resp.text[:100]}")
                except Exception:
                    errors.append(f"invalid_json:{url}:{resp.status_code}")
            else:
                errors.append(f"status_{resp.status_code}:{url}")
        except Exception as exc:
            errors.append(f"exc:{url}:{exc.__class__.__name__}")
    return [], ";".join(errors)


def load_series_events(series_id: str, api_key: Optional[str] = None, cache_dir: Optional[str] = None) -> EventLoadResult:
    if not series_id:
        return EventLoadResult(events=[], meta={"reason": "series_id_required"})
    key = api_key or os.getenv("GRID_API_KEY")
    if not key:
        return EventLoadResult(events=[], meta={"reason": "missing_api_key"})

    cache_root = pathlib.Path(cache_dir or (pathlib.Path(tempfile.gettempdir()) / "grid_file_download"))
    cache_root.mkdir(parents=True, exist_ok=True)

    files, source_url = _list_files(key, series_id)
    meta: Dict[str, Any] = {
        "series_id": series_id,
        "source": source_url,
        "event_count": 0,
        "title": None,
        "file_type": None,
    }
    if not files:
        meta["reason"] = source_url or "no_files"
        return EventLoadResult(events=[], meta=meta)

    target = _pick_file(files)
    if not target:
        meta["reason"] = "no_event_file"
        return EventLoadResult(events=[], meta=meta)

    url = target.get("file_url") or target.get("downloadUrl") or target.get("url") or target.get("href") or target.get("fullURL")
    file_name = target.get("file_name") or target.get("fileName") or target.get("name") or f"series_{series_id}.json"
    meta["title"] = target.get("title") or target.get("gameTitle") or target.get("type")
    meta["file_type"] = pathlib.Path(file_name).suffix

    if not url:
        meta["reason"] = "missing_download_url"
        return EventLoadResult(events=[], meta=meta)

    dest = cache_root / file_name
    try:
        resp = requests.get(url, headers={"x-api-key": key}, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    except Exception as exc:
        meta["reason"] = f"download_failed:{exc.__class__.__name__}"
        return EventLoadResult(events=[], meta=meta)

    events, extra_meta = _extract_events_from_file(dest)
    meta.update(extra_meta)
    if not events:
        meta.setdefault("reason", "parsed_zero_events")
    return EventLoadResult(events=events, meta=meta)


def list_series_files(series_id: str, api_key: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not series_id:
        return [], {"reason": "series_id_required"}
    key = api_key or os.getenv("GRID_API_KEY")
    if not key:
        return [], {"reason": "missing_api_key"}
    files, source = _list_files(key, series_id)
    meta = {"series_id": series_id, "source": source}
    if not files:
        meta["reason"] = source or "no_files"
    return files, meta
