from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Tuple

from driftcoach.adapters.grid.file_download_client import RawEvent


def _round_key(ev: RawEvent) -> Optional[int]:
    r = ev.round
    if r is None:
        payload = ev.payload or {}
        r = payload.get("roundNumber") or payload.get("round") or payload.get("round_num")
        if r is None:
            segs = None
            if isinstance(payload.get("seriesStateDelta"), dict):
                ssd = payload["seriesStateDelta"]
                segs = ssd.get("segments")
                if not segs:
                    for g in ssd.get("games") or []:
                        segs = g.get("segments")
                        if segs:
                            break
            if not segs and isinstance(payload.get("seriesState"), dict):
                ss = payload["seriesState"]
                segs = ss.get("segments")
                if not segs:
                    for g in ss.get("games") or []:
                        segs = g.get("segments")
                        if segs:
                            break
            if isinstance(segs, list) and segs:
                seq = segs[0].get("sequenceNumber") or segs[0].get("sequence")
                if seq is not None:
                    r = seq
    try:
        return int(r)
    except Exception:
        return None


def _collect_team_ids(payload: Dict[str, Any]) -> List[str]:
    teams: List[str] = []
    for path in ["seriesState", "seriesStateDelta"]:
        ss = payload.get(path)
        if isinstance(ss, dict):
            for container in ["games", "segments"]:
                for item in ss.get(container) or []:
                    for t in item.get("teams") or []:
                        tid = t.get("id")
                        if tid:
                            teams.append(str(tid))
    return teams


def _team_from_payload(payload: Dict[str, Any], role: str = "team") -> Optional[str]:
    keys = [role, f"{role}Id", f"{role}_id", f"{role}ID", f"{role}TeamId", f"{role}Team"]
    for k in keys:
        val = payload.get(k)
        if val:
            return str(val)
    return None


def _actor_team(payload: Dict[str, Any]) -> Optional[str]:
    actor = payload.get("actor")
    if isinstance(actor, dict):
        if actor.get("type") == "team" and actor.get("id"):
            return str(actor.get("id"))
        state = actor.get("state") or actor.get("stateDelta")
        if isinstance(state, dict):
            tid = state.get("teamId") or state.get("team")
            if tid:
                return str(tid)
    return _team_from_payload(payload, role="team")


def _target_team(payload: Dict[str, Any]) -> Optional[str]:
    target = payload.get("target")
    if isinstance(target, dict):
        if target.get("type") == "team" and target.get("id"):
            return str(target.get("id"))
        state = target.get("state") or target.get("stateDelta")
        if isinstance(state, dict):
            tid = state.get("teamId") or state.get("team")
            if tid:
                return str(tid)
    return _team_from_payload(payload, role="targetTeam")


def _winner_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    direct = _team_from_payload(payload, role="winningTeam") or payload.get("winner") or payload.get("winnerTeam")
    if direct:
        return str(direct)
    actor = payload.get("actor")
    if isinstance(actor, dict):
        for state_key in ["state", "stateDelta"]:
            st = actor.get(state_key)
            if not isinstance(st, dict):
                continue
            for container in ["teams"]:
                for t in st.get(container) or []:
                    if t.get("won") and t.get("id"):
                        return str(t.get("id"))
            for g in st.get("games") or []:
                for t in g.get("teams") or []:
                    if t.get("won") and t.get("id"):
                        return str(t.get("id"))
                for seg in g.get("segments") or []:
                    for t in seg.get("teams") or []:
                        if t.get("won") and t.get("id"):
                            return str(t.get("id"))
            for seg in st.get("segments") or []:
                for t in seg.get("teams") or []:
                    if t.get("won") and t.get("id"):
                        return str(t.get("id"))
    # series state segments may hold winners
    for path in ["seriesState", "seriesStateDelta"]:
        ss = payload.get(path)
        if isinstance(ss, dict):
            for seg in ss.get("segments") or []:
                for t in seg.get("teams") or []:
                    if t.get("won"):
                        tid = t.get("id")
                        if tid:
                            return str(tid)
    return None


def _md5(payload: Any) -> str:
    return hashlib.md5(str(payload).encode("utf-8")).hexdigest()[:10]


def compress_events_to_facts(series_id: str, events: List[RawEvent]) -> List[Dict[str, Any]]:
    if not series_id or not events:
        return []

    rounds: Dict[int, Dict[str, Any]] = defaultdict(
        lambda: {"events": [], "kills": defaultdict(int), "deaths": defaultdict(int), "teams": set(), "game_index": None}
    )
    for ev in events:
        rk = _round_key(ev)
        payload = ev.payload or {}
        team = _actor_team(payload) or _team_from_payload(payload, role="actorTeam")
        target_team = _target_team(payload) or _team_from_payload(payload, role="victimTeam")
        game_idx = None
        ss = payload.get("seriesState") or payload.get("seriesStateDelta")

        def _record_econ(team_obj: Dict[str, Any], round_hint: Optional[int] = None, game_hint: Optional[int] = None) -> None:
            if not isinstance(team_obj, dict):
                return
            tid = team_obj.get("id") or team_obj.get("teamId")
            if not tid:
                return
            bucket.setdefault("economy", []).append(
                {
                    "teamId": str(tid),
                    "money": team_obj.get("money"),
                    "loadoutValue": team_obj.get("loadoutValue"),
                    "netWorth": team_obj.get("netWorth"),
                    "players": team_obj.get("players") or [],
                    "roundNumber": round_hint,
                    "gameIndex": game_hint,
                }
            )

        if isinstance(ss, dict):
            for g in ss.get("games") or []:
                if g.get("sequenceNumber") is not None:
                    game_idx = g.get("sequenceNumber")

        bucket = rounds[rk if rk is not None else -1]
        bucket["events"].append(ev)
        if game_idx is not None:
            bucket["game_index"] = game_idx
        for tid in _collect_team_ids(payload):
            bucket["teams"].add(tid)
        if ev.kind == "KILL_DEATH":
            if team:
                bucket["kills"][team] += 1
            if target_team:
                bucket["deaths"][target_team] += 1
            if team and target_team and team != target_team and not bucket.get("first_kill_team"):
                bucket["first_kill_team"] = team
                bucket["first_kill_victim_team"] = target_team
        if ev.kind == "ROUND_END":
            bucket["winner"] = _winner_from_payload(payload) or team
            bucket["loser"] = payload.get("loser") or payload.get("losingTeam") or payload.get("defeatedTeam")
        if ev.kind == "OBJECTIVE":
            bucket.setdefault("objectives", []).append(payload)
        if ev.kind == "ECONOMY_SNAPSHOT":
            bucket.setdefault("economy", []).append(payload)

        if isinstance(ss, dict):
            for t in ss.get("teams") or []:
                _record_econ(t)
            for seg in ss.get("segments") or []:
                seq = seg.get("sequenceNumber") or seg.get("sequence")
                for t in seg.get("teams") or []:
                    _record_econ(t, round_hint=seq)
            for g in ss.get("games") or []:
                gseq = g.get("sequenceNumber") or g.get("game")
                for t in g.get("teams") or []:
                    _record_econ(t, game_hint=gseq)
                for seg in g.get("segments") or []:
                    seq = seg.get("sequenceNumber") or seg.get("sequence")
                    for t in seg.get("teams") or []:
                        _record_econ(t, round_hint=seq, game_hint=gseq)

        # Infer loser from segments when winner known
        if ev.kind == "ROUND_END" and bucket.get("winner") and not bucket.get("loser"):
            segs = None
            if isinstance(payload.get("seriesStateDelta"), dict):
                segs = payload["seriesStateDelta"].get("segments")
            if not segs and isinstance(payload.get("seriesState"), dict):
                segs = payload["seriesState"].get("segments")
            if isinstance(segs, list) and segs:
                teams_in_seg = segs[0].get("teams") or []
                candidates = [str(t.get("id")) for t in teams_in_seg if t.get("id")]
                others = [c for c in candidates if c != bucket.get("winner")]
                if others:
                    bucket["loser"] = others[0]

    # second pass loser inference using team set
    for bucket in rounds.values():
        if bucket.get("winner") and not bucket.get("loser") and len(bucket.get("teams") or []) >= 2:
            others = [t for t in bucket["teams"] if t != bucket.get("winner")]
            if others:
                bucket["loser"] = others[0]

    facts: List[Dict[str, Any]] = []

    # Helper to register fact
    def add_fact(
        fact_type: str,
        game_index: Optional[int],
        round_range: Tuple[int, int],
        evs: List[RawEvent],
        confidence: str,
        note: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        facts.append(
            {
                "fact_type": fact_type,
                "series_id": series_id,
                "game_index": game_index,
                "round_range": [round_range[0], round_range[1]],
                "evidence_events": [e.payload for e in evs],
                "confidence": confidence,
                "derived_from": "file_download",
                "fact_id": f"fact_{fact_type.lower()}_{_md5(round_range)}",
                "note": note,
                **(extra or {}),
            }
        )
    # Economy-driven facts (FORCE_BUY_ROUND, FULL_BUY_ROUND, ECO_COLLAPSE_SEQUENCE)
    econ_by_round_team: Dict[int, Dict[str, Dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {"entries": [], "game_index": None, "winner": None, "loser": None}))
    for rk, bucket in rounds.items():
        econ_entries = bucket.get("economy") or []
        for econ in econ_entries:
            rr = econ.get("roundNumber")
            rr = int(rr) if rr is not None else rk
            if rr is None:
                continue
            tid = econ.get("teamId") or econ.get("team")
            if not tid:
                continue
            rec = econ_by_round_team[rr][str(tid)]
            rec["entries"].append(econ)
            if bucket.get("game_index") is not None:
                rec["game_index"] = bucket.get("game_index")
            elif econ.get("gameIndex") is not None:
                rec["game_index"] = econ.get("gameIndex")
            rec["winner"] = rec.get("winner") or bucket.get("winner")
            rec["loser"] = rec.get("loser") or bucket.get("loser")
        # propagate winner/loser even if no econ entries
        if bucket.get("winner") and bucket.get("loser"):
            for tid in list(bucket.get("teams") or []):
                rec = econ_by_round_team[rk][str(tid)]
                rec["winner"] = bucket.get("winner")
                rec["loser"] = bucket.get("loser")
                rec["game_index"] = rec.get("game_index") or bucket.get("game_index")

    def _aggregate_snapshot(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        team_money = None
        team_loadout = None
        team_networth = None
        players: List[Dict[str, Any]] = []
        for e in entries:
            if e.get("money") is not None:
                try:
                    team_money = float(e.get("money")) if team_money is None else max(team_money, float(e.get("money")))
                except Exception:
                    pass
            if e.get("loadoutValue") is not None:
                try:
                    team_loadout = float(e.get("loadoutValue")) if team_loadout is None else max(team_loadout, float(e.get("loadoutValue")))
                except Exception:
                    pass
            if e.get("netWorth") is not None:
                try:
                    team_networth = float(e.get("netWorth")) if team_networth is None else max(team_networth, float(e.get("netWorth")))
                except Exception:
                    pass
            if isinstance(e.get("players"), list):
                players.extend(e.get("players"))
        player_loadouts = []
        player_money = []
        normalized_players = []
        for p in players:
            if not isinstance(p, dict):
                continue
            pid = p.get("id") or p.get("playerId")
            lv = p.get("loadoutValue")
            mo = p.get("money")
            if lv is not None:
                try:
                    player_loadouts.append(float(lv))
                except Exception:
                    pass
            if mo is not None:
                try:
                    player_money.append(float(mo))
                except Exception:
                    pass
            normalized_players.append({"id": pid, "loadoutValue": lv, "money": mo})
        avg_player_loadout = sum(player_loadouts) / len(player_loadouts) if player_loadouts else None
        avg_player_money = sum(player_money) / len(player_money) if player_money else None
        team_avg_loadout = team_loadout if team_loadout is not None else avg_player_loadout
        team_avg_money = team_money if team_money is not None else avg_player_money
        return {
            "team_avg_loadout": team_avg_loadout,
            "team_avg_money": team_avg_money,
            "team_networth": team_networth,
            "players": normalized_players,
        }

    team_recent_loadouts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=6))
    player_recent_max: Dict[str, float] = defaultdict(float)
    collapse_chain: Dict[str, List[int]] = defaultdict(list)

    for rr in sorted([rk for rk in econ_by_round_team.keys() if rk is not None]):
        for team_id, rec in econ_by_round_team[rr].items():
            snapshot = _aggregate_snapshot(rec["entries"])
            team_loadout = snapshot.get("team_avg_loadout")
            team_money = snapshot.get("team_avg_money")
            players = snapshot.get("players") or []
            recent_vals = list(team_recent_loadouts[team_id])
            baseline = max(recent_vals) if recent_vals else team_loadout
            if baseline and team_loadout is not None:
                loadout_ratio = team_loadout / baseline if baseline else 0
            else:
                loadout_ratio = None

            # FULL_BUY_ROUND
            if baseline and team_loadout is not None and team_loadout >= 0.9 * baseline:
                add_fact(
                    "FULL_BUY_ROUND",
                    rec.get("game_index"),
                    (rr, rr),
                    [],
                    "medium",
                    extra={"team_id": team_id, "round": rr, "loadout_ratio": loadout_ratio},
                )

            # FORCE_BUY_ROUND
            players_full_buy = 0
            for p in players:
                pid = p.get("id")
                lv = p.get("loadoutValue")
                if pid is None or lv is None:
                    continue
                try:
                    lv_f = float(lv)
                except Exception:
                    continue
                baseline_player = player_recent_max.get(str(pid)) or lv_f
                if baseline_player and lv_f >= 0.7 * baseline_player:
                    players_full_buy += 1
                if lv_f > player_recent_max.get(str(pid), 0):
                    player_recent_max[str(pid)] = lv_f

            eco_threshold_mid = 0.55 * baseline if baseline else None
            if baseline and team_loadout is not None and eco_threshold_mid is not None:
                if team_loadout < eco_threshold_mid and players_full_buy >= 2:
                    result = "UNKNOWN"
                    if rec.get("winner"):
                        result = "SUCCESS" if rec.get("winner") == team_id else "FAIL"
                    add_fact(
                        "FORCE_BUY_ROUND",
                        rec.get("game_index"),
                        (rr, rr),
                        [],
                        "medium",
                        extra={
                            "team_id": team_id,
                            "round": rr,
                            "result": result,
                            "economy_context": {
                                "team_loadout_ratio": loadout_ratio,
                                "players_full_buy_count": players_full_buy,
                                "team_money": team_money,
                            },
                        },
                    )

            # ECO_COLLAPSE_SEQUENCE tracking (low-econ run until recovery)
            if loadout_ratio is not None and loadout_ratio < 0.55:
                collapse_chain[team_id].append(rr)
            else:
                if len(collapse_chain[team_id]) >= 2:
                    rounds_span = collapse_chain[team_id]
                    add_fact(
                        "ECO_COLLAPSE_SEQUENCE",
                        rec.get("game_index"),
                        (rounds_span[0], rounds_span[-1]),
                        [],
                        "medium",
                        extra={"team_id": team_id, "rounds": rounds_span, "severity": "HIGH" if len(rounds_span) >= 3 else "MEDIUM"},
                    )
                collapse_chain[team_id] = []

            if team_loadout is not None:
                team_recent_loadouts[team_id].append(team_loadout)

    # flush remaining collapse chains
    for team_id, seq in collapse_chain.items():
        if len(seq) >= 2:
            add_fact(
                "ECO_COLLAPSE_SEQUENCE",
                None,
                (seq[0], seq[-1]),
                [],
                "medium",
                extra={"team_id": team_id, "rounds": seq, "severity": "HIGH" if len(seq) >= 3 else "MEDIUM"},
            )

    # ROUND_SWING & HIGH_RISK_SEQUENCE & OBJECTIVE_LOSS_CHAIN
    sorted_rounds = sorted([rk for rk in rounds.keys() if rk is not None])
    loss_chain: Dict[str, List[int]] = defaultdict(list)
    death_surplus_chain: Dict[str, List[int]] = defaultdict(list)
    for rk in sorted_rounds:
        bucket = rounds[rk]
        winner = bucket.get("winner")
        loser = bucket.get("loser")
        kills = bucket.get("kills", {})
        deaths = bucket.get("deaths", {})
        if winner and loser:
            loss_chain[loser].append(rk)
        for team_id, death_ct in deaths.items():
            kill_ct = kills.get(team_id, 0)
            if death_ct - kill_ct >= 2:
                death_surplus_chain[team_id].append(rk)
        # Round swing: opening advantage flips outcome
        opening_team = bucket.get("first_kill_team")
        if winner and opening_team and winner != opening_team:
            evs = [e for e in bucket.get("events", []) if _round_key(e) == rk]
            add_fact(
                "ROUND_SWING",
                bucket.get("game_index"),
                (rk, rk),
                evs,
                "high",
                note=f"opening_team={opening_team} winner={winner}",
                extra={"opening_team": opening_team, "winner": winner},
            )
        elif winner and loser:
            win_k = kills.get(winner, 0)
            lose_k = kills.get(loser, 0)
            if lose_k > win_k:
                evs = [e for e in bucket.get("events", []) if _round_key(e) == rk]
                add_fact(
                    "ROUND_SWING",
                    bucket.get("game_index"),
                    (rk, rk),
                    evs,
                    "medium",
                    note=f"loser_kills={lose_k} winner_kills={win_k}",
                    extra={"opening_team": opening_team, "winner": winner},
                )
        # objective loss chain detection accumulation happens after loop

    for team_id, rounds_lost in loss_chain.items():
        if len(rounds_lost) >= 2:
            add_fact(
                "OBJECTIVE_LOSS_CHAIN",
                None,
                (rounds_lost[0], rounds_lost[-1]),
                [],
                "medium",
                note=f"team {team_id} lost {len(rounds_lost)} objective rounds",
            )

    for team_id, rounds_high in death_surplus_chain.items():
        if len(rounds_high) >= 3:
            add_fact(
                "HIGH_RISK_SEQUENCE",
                None,
                (rounds_high[0], rounds_high[-1]),
                [],
                "medium",
                note=f"team {team_id} deaths >> kills",
            )

    return facts
