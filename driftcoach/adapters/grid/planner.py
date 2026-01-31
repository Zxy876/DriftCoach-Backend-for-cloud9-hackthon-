import datetime as dt
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .client import GridClient
from .file_download_client import load_series_events


logger = logging.getLogger(__name__)


OUTCOME_CANDIDATES = ["winner", "teams.score", "result", "outcome"]
MAX_STEPS = 6
ALLSERIES_LIMIT = 200
WINDOW_DAYS = 90
WINDOW_EXPANSION_DAYS = 180


@dataclass
class PlanStep:
    id: str
    name: str
    query: str
    variables: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    series_id: str
    player_id: str
    max_steps: int = MAX_STEPS
    steps: List[PlanStep] = field(default_factory=list)
    window_days: int = WINDOW_DAYS


def _iso(dt_obj: dt.datetime) -> str:
    return dt_obj.replace(microsecond=0).isoformat() + "Z"


def _safe_get(dct: Dict[str, Any], path: str) -> Optional[Any]:
    cur = dct
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                idx = int(part)
                cur = cur[idx]
            except Exception:
                return None
            continue
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


def build_plan(series_id: str, player_id: str, max_steps: int = MAX_STEPS) -> Plan:
    return Plan(series_id=series_id, player_id=player_id, max_steps=max_steps)


def _introspection_query() -> str:
    return (
        """
        query Introspect {
          queryType: __schema { queryType { fields { name } } }
          seriesType: __type(name: "Series") { fields { name } }
        }
        """
    )


def _extract_field_set(resp: Dict[str, Any], key: str) -> set:
    fields = resp.get("data", {}).get(key, {})
    names = fields.get("fields") or []
    return {f.get("name") for f in names if isinstance(f, dict) and f.get("name")}


def _build_series_selection(series_fields: set) -> str:
    parts = ["id"]
    if "title" in series_fields:
        parts.append("title { name }")
    if "tournament" in series_fields:
        parts.append("tournament { name id }")
    if "format" in series_fields:
        parts.append("format { name id }")
    if "startTimeScheduled" in series_fields:
        parts.append("startTimeScheduled")
    if "startTime" in series_fields:
        parts.append("startTime")
    if "teams" in series_fields:
        parts.append("teams { baseInfo { id name } }")
    if "winner" in series_fields:
        parts.append("winner { id name }")
    if "result" in series_fields:
        parts.append("result")
    if "outcome" in series_fields:
        parts.append("outcome")
    if "games" in series_fields:
        parts.append("games { id sequenceNumber }")
    return "\n      ".join(parts)


def _series_anchor_query(series_fields: set) -> str:
    selection = _build_series_selection(series_fields)
    return f"""
    query AnchorSeries($id: ID!) {{
      series(id: $id) {{
        {selection}
      }}
    }}
    """


def _player_query(query_fields: set) -> Optional[str]:
    if "player" not in query_fields:
        return None
    return (
        """
        query PlayerBasic($id: ID!) {
          player(id: $id) { id name ign }
        }
        """
    )


def _all_series_query(series_fields: set, use_first: bool = True) -> str:
    selection = _build_series_selection(series_fields)
    paging = "first: 200" if use_first else ""
    return f"""
    query SeriesPool($filter: SeriesFilter) {{
      allSeries(filter: $filter {',' if paging else ''}{paging}) {{
        {selection}
      }}
    }}
    """


def execute_plan(plan: Plan, client: GridClient) -> Dict[str, Any]:
    cache: Dict[str, Any] = {}
    facts: Dict[str, Any] = {"plan": plan, "steps": [], "errors": []}

    def run(query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        key = json.dumps({"q": query, "v": variables}, sort_keys=True)
        if key in cache:
            return cache[key]
        resp = client.run_query(query, variables)
        cache[key] = resp
        return resp

    # Step 0: introspection
    intro_query = _introspection_query()
    try:
        introspection = run(intro_query, {})
        series_fields = _extract_field_set(introspection, "seriesType")
        query_fields = _extract_field_set(introspection, "queryType")
        facts["introspection"] = {
            "series_fields": sorted(series_fields),
            "query_fields": sorted(query_fields),
        }
    except Exception as exc:  # pragma: no cover
        facts["introspection_error"] = str(exc)
        # Fallback assumptions to proceed
        series_fields = {
            "id",
            "startTimeScheduled",
            "tournament",
            "format",
            "teams",
        }
        query_fields = {"series", "allSeries", "player"}
        facts["introspection"] = {
            "series_fields": sorted(series_fields),
            "query_fields": sorted(query_fields),
            "fallback": True,
        }
    logger.info(
        "[INTROSPECT] series_fields=%s query_fields=%s fallback=%s",
        facts["introspection"].get("series_fields"),
        facts["introspection"].get("query_fields"),
        facts["introspection"].get("fallback", False),
    )

    # Step 1: Anchor series
    series_query = _series_anchor_query(series_fields)
    anchor_resp = run(series_query, {"id": plan.series_id})
    anchor_series = (anchor_resp.get("data", {}) or {}).get("series") or {}
    games = anchor_series.get("games") or []
    logger.info(
        "[CENTRAL_DATA] series=%s games_count=%s sample=%s",
        plan.series_id,
        len(games),
        [{"id": g.get("id"), "seq": g.get("sequenceNumber")} for g in games[:3]],
    )

    if not games:
        try:
            fd_result = load_series_events(plan.series_id, api_key=getattr(client, "api_key", None))
            meta = fd_result.meta if isinstance(fd_result.meta, dict) else {}
            logger.info(
                "[FILE_DOWNLOAD] fallback_for_games series=%s triggered_by=central_data_empty event_count=%s source=%s reason=%s",
                plan.series_id,
                meta.get("event_count"),
                meta.get("source"),
                meta.get("reason"),
            )

            seen = set()
            fallback_games: List[Dict[str, Any]] = []
            for ev in fd_result.events:
                payload = ev.payload or {}
                gid = payload.get("gameId") or payload.get("game_id") or payload.get("matchId") or payload.get("match_id")
                seq = (
                    payload.get("sequenceNumber")
                    or payload.get("gameSequenceNumber")
                    or payload.get("gameNumber")
                    or payload.get("mapNumber")
                    or payload.get("game")
                )
                key = (gid, seq)
                if key in seen:
                    continue
                seen.add(key)
                if gid or seq is not None:
                    fallback_games.append({"id": gid, "sequenceNumber": seq})

            if fallback_games:
                anchor_series["games"] = fallback_games
                facts["fallback_games"] = fallback_games
        except Exception as exc:  # pragma: no cover
            logger.warning("[FILE_DOWNLOAD] fallback_failed series=%s error=%s", plan.series_id, exc)
    facts["anchor_series"] = anchor_series
    facts["steps"].append({"id": "anchor", "fields_used": list(series_fields)})

    # Step 2: Player (optional)
    player_payload: Optional[Dict[str, Any]] = None
    player_query = _player_query(query_fields)
    roster_proxy = "SKIPPED"
    if player_query:
        try:
            resp = run(player_query, {"id": plan.player_id})
            player_payload = (resp.get("data", {}) or {}).get("player")
        except Exception as exc:  # pragma: no cover
            facts["errors"].append({"step": "player", "error": str(exc)})
            player_payload = None
    else:
        facts["errors"].append({"step": "player", "error": "player field missing"})
    facts["player"] = player_payload
    if "players" not in query_fields:
        roster_proxy = "UNAVAILABLE"
    facts["roster_proxy"] = roster_proxy

    # Step 3: compute window
    start_raw = anchor_series.get("startTimeScheduled") or anchor_series.get("startTime")
    window_days = plan.window_days
    window_expanded = False
    if start_raw:
        try:
            start_dt = dt.datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
        except Exception:
            start_dt = dt.datetime.utcnow()
    else:
        start_dt = dt.datetime.utcnow()
    gte = _iso(start_dt - dt.timedelta(days=window_days))
    lte = _iso(start_dt + dt.timedelta(days=window_days))

    # Step 4: enumerate pool
    series_pool: List[Dict[str, Any]] = []
    filter_payload = {"startTimeScheduled": {"gte": gte, "lte": lte}}
    if "allSeries" in query_fields:
        for attempt in (True, False):
            try:
                pool_query = _all_series_query(series_fields, use_first=attempt)
                resp = run(pool_query, {"filter": filter_payload})
                pool = (resp.get("data", {}) or {}).get("allSeries") or []
                series_pool = pool if isinstance(pool, list) else pool if isinstance(pool, dict) else []
                break
            except Exception as exc:  # pragma: no cover
                facts["errors"].append({"step": "allSeries", "error": str(exc), "attempt_with_first": attempt})
                continue
    else:
        facts["errors"].append({"step": "allSeries", "error": "allSeries field missing"})

    # limit edges
    if isinstance(series_pool, list) and len(series_pool) > ALLSERIES_LIMIT:
        series_pool = series_pool[:ALLSERIES_LIMIT]

    # Step 4b: expand window once if pool small and start present
    if len(series_pool) < 10 and not window_expanded:
        window_expanded = True
        gte = _iso(start_dt - dt.timedelta(days=WINDOW_EXPANSION_DAYS))
        lte = _iso(start_dt + dt.timedelta(days=WINDOW_EXPANSION_DAYS))
        filter_payload = {"startTimeScheduled": {"gte": gte, "lte": lte}}
        if "allSeries" in query_fields:
            try:
                pool_query = _all_series_query(series_fields, use_first=True)
                resp = run(pool_query, {"filter": filter_payload})
                pool = (resp.get("data", {}) or {}).get("allSeries") or []
                series_pool = pool if isinstance(pool, list) else pool if isinstance(pool, dict) else series_pool
            except Exception as exc:  # pragma: no cover
                facts["errors"].append({"step": "allSeries_expand", "error": str(exc)})

    facts["series_pool_raw"] = series_pool
    facts["window"] = {"gte": gte, "lte": lte, "expanded": window_expanded}

    # Step 5: local narrowing
    def _team_names(item):
        teams = item.get("teams") or []
        names = []
        for t in teams:
            for key in ("name",):
                if t.get(key):
                    names.append(str(t.get(key)))
            base = t.get("baseInfo") or {}
            if base.get("name"):
                names.append(str(base.get("name")))
        return set(names)

    anchor_teams = _team_names(anchor_series)
    anchor_tournament = None
    if isinstance(anchor_series.get("tournament"), dict):
        anchor_tournament = anchor_series.get("tournament", {}).get("name")
    elif anchor_series.get("tournament"):
        anchor_tournament = anchor_series.get("tournament")
    anchor_format = None
    fmt = anchor_series.get("format")
    if isinstance(fmt, dict):
        anchor_format = fmt.get("name")
    elif fmt:
        anchor_format = fmt

    narrowed: List[Dict[str, Any]] = []
    for item in series_pool or []:
        keep = False
        if anchor_tournament and (item.get("tournament") or {}).get("name") == anchor_tournament:
            keep = True
        fmt_item = item.get("format") or {}
        fmt_name = fmt_item.get("name") if isinstance(fmt_item, dict) else fmt_item
        if anchor_format and fmt_name == anchor_format:
            keep = True
        if anchor_teams and (_team_names(item) & anchor_teams):
            keep = True
        if keep:
            narrowed.append(item)

    facts["series_pool"] = series_pool
    facts["narrowed"] = narrowed
    facts["counts"] = {
        "pool": len(series_pool or []),
        "narrowed": len(narrowed),
        "anchor_teams": len(anchor_teams),
    }

    # Step 6: outcome detection
    outcome_field = None
    missing_fields: List[str] = []
    series_candidates = [anchor_series] + list(narrowed)
    for candidate in OUTCOME_CANDIDATES:
        if "." in candidate:
            base, sub = candidate.split(".")
            has_value = any(
                bool(_safe_get(item, f"{base}.0.{sub}")) or bool(_safe_get(item, f"{base}.{sub}"))
                for item in series_candidates
            )
        else:
            has_value = any(bool(item.get(candidate)) for item in series_candidates)
        if has_value:
            outcome_field = candidate
            break
        missing_fields.append(candidate)

    facts["outcome_field"] = outcome_field or "NOT_FOUND"
    facts["missing_outcome_fields"] = missing_fields if not outcome_field else []

    # Step 7: aggregated statistics (team / player)
    team_stats_info: Dict[str, Any] = {"reason": "field_missing"}
    player_stats_info: Dict[str, Any] = {"reason": "field_missing"}

    def _extract_ids(series_obj: Dict[str, Any]) -> List[str]:
        teams = series_obj.get("teams") or []
        ids: List[str] = []
        for t in teams:
            base = t.get("baseInfo") or {}
            if base.get("id"):
                ids.append(str(base.get("id")))
        return ids

    anchor_team_ids = _extract_ids(anchor_series)

    if "teamStatistics" in query_fields:
        team_stats_info = {"reason": "query_failed", "query_name": "teamStatistics"}
        try:
            team_query = """
            query TeamStats($seriesId: ID!, $teamIds: [ID!]) {
              teamStatistics(filter: { seriesIds: [$seriesId], teamIds: $teamIds }) {
                aggregationSeriesIds
              }
            }
            """
            resp = run(team_query, {"seriesId": plan.series_id, "teamIds": anchor_team_ids or None})
            data = (resp.get("data", {}) or {}).get("teamStatistics")
            agg_ids = None
            if isinstance(data, dict):
                agg_ids = data.get("aggregationSeriesIds")
            team_stats_info = {
                "data": data,
                "reason": "ok" if data else "empty",
                "aggregation_series_ids": agg_ids,
                "query_name": "teamStatistics",
            }
        except Exception as exc:  # pragma: no cover
            facts["errors"].append({"step": "teamStatistics", "error": str(exc)})
            team_stats_info["reason"] = str(exc)
    else:
        facts["errors"].append({"step": "teamStatistics", "error": "teamStatistics field missing"})

    if "playerStatistics" in query_fields:
        player_stats_info = {"reason": "query_failed", "query_name": "playerStatistics"}
        try:
            player_query = """
            query PlayerStats($seriesId: ID!, $playerId: ID!) {
              playerStatistics(filter: { seriesIds: [$seriesId], playerIds: [$playerId] }) {
                aggregationSeriesIds
              }
            }
            """
            resp = run(player_query, {"seriesId": plan.series_id, "playerId": plan.player_id})
            data = (resp.get("data", {}) or {}).get("playerStatistics")
            agg_ids = None
            if isinstance(data, dict):
                agg_ids = data.get("aggregationSeriesIds")
            player_stats_info = {
                "data": data,
                "reason": "ok" if data else "empty",
                "aggregation_series_ids": agg_ids,
                "query_name": "playerStatistics",
            }
        except Exception as exc:  # pragma: no cover
            facts["errors"].append({"step": "playerStatistics", "error": str(exc)})
            player_stats_info["reason"] = str(exc)
    else:
        facts["errors"].append({"step": "playerStatistics", "error": "playerStatistics field missing"})

    facts["team_statistics"] = team_stats_info
    facts["player_statistics"] = player_stats_info

    logger.info(
        "[PLAN] steps=%s series=%s player=%s window=%s outcome_field=%s pool=%s narrowed=%s",
        len(facts.get("steps", [])),
        plan.series_id,
        plan.player_id,
        facts.get("window"),
        facts.get("outcome_field"),
        facts["counts"].get("pool"),
        facts["counts"].get("narrowed"),
    )

    return facts
