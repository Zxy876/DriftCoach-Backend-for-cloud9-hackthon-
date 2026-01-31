import os, json, datetime as dt, requests, time
from driftcoach.adapters.grid.client import GridClient
from driftcoach.adapters.grid import queries as q
from driftcoach.adapters.grid.rate_budget import reset_grid_controls

def main():
    api_key = os.getenv('GRID_API_KEY')
    if not api_key:
        raise SystemExit('no api key')
    reset_grid_controls()
    cli = GridClient(api_key=api_key)
    now = dt.datetime.utcnow()
    gte = (now - dt.timedelta(days=180)).isoformat() + 'Z'
    lte = (now + dt.timedelta(days=180)).isoformat() + 'Z'
    try:
        series_payload = cli.run_query(q.Q_ALL_SERIES_WINDOW, {"gte": gte, "lte": lte, "first": 10})
        edges = (series_payload.get('data', {}) or {}).get('allSeries', {}).get('edges') or []
    except Exception as exc:
        print('series fetch failed', exc)
        return
    player_ids = []
    for edge in edges:
        node = edge.get('node') or {}
        teams = node.get('teams') or []
        for t in teams:
            base = t.get('baseInfo') or {}
            tid = base.get('id')
            if not tid:
                continue
            try:
                roster = cli.run_query(q.Q_TEAM_ROSTER, {"teamId": tid})
            except Exception as exc:
                print('roster fetch failed', tid, exc)
                reset_grid_controls()
                cli = GridClient(api_key=api_key)
                continue
            for e in (roster.get('data', {}) or {}).get('players', {}).get('edges') or []:
                n = e.get('node') or {}
                pid = n.get('id')
                if pid:
                    player_ids.append(pid)
    player_ids = list(dict.fromkeys(player_ids))[:15]
    print("testing players", len(player_ids))
    url = 'https://api-op.grid.gg/statistics-feed/graphql'
    headers = {'x-api-key': api_key, 'Content-Type': 'application/json'}
    found = None
    checked = 0
    for pid in player_ids:
        body = {
            "query": "query PlayerStatisticsForLastThreeMonths($playerId: ID!) { playerStatistics(playerId: $playerId, filter: { timeWindow: LAST_3_MONTHS }) { id aggregationSeriesIds series { count kills { sum min max avg } } game { count wins { value count percentage streak { min max current } } } segment { type count deaths { sum min max avg } } } }",
            "variables": {"playerId": pid},
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=20)
            data = resp.json()
        except Exception as exc:
            print('err', pid, exc)
            continue
        checked += 1
        stats = ((data.get('data') or {}).get('playerStatistics')) if isinstance(data, dict) else None
        agg = stats.get('aggregationSeriesIds') if isinstance(stats, dict) else []
        if agg:
            found = {'player_id': pid, 'aggregationSeriesIds': agg, 'series': stats.get('series'), 'game': stats.get('game')}
            break
        time.sleep(0.2)
    print(json.dumps({'found': found, 'tested': checked, 'player_sample': player_ids}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
