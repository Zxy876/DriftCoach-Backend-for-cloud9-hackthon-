import os, json, requests
from driftcoach.adapters.grid.client import GridClient
from driftcoach.adapters.grid import queries as q
from driftcoach.adapters.grid.rate_budget import reset_grid_controls

api_key = os.getenv('GRID_API_KEY')
if not api_key:
    raise SystemExit('no api key')
reset_grid_controls()
cli = GridClient(api_key=api_key)
players_payload = cli.run_query(q.Q_PLAYERS, {"first": 30, "after": None})
edges = (players_payload.get('data', {}) or {}).get('players', {}).get('edges') or []
player_ids = [(e.get('node') or {}).get('id') for e in edges if (e.get('node') or {}).get('id')]
print('sample players', player_ids)

url = 'https://api-op.grid.gg/statistics-feed/graphql'
headers = {'x-api-key': api_key, 'Content-Type': 'application/json'}
found = None
for pid in player_ids:
    body = {
        "query": "query PlayerStatisticsForLastThreeMonths($playerId: ID!) { playerStatistics(playerId: $playerId, filter: { timeWindow: LAST_3_MONTHS }) { id aggregationSeriesIds series { count kills { sum min max avg } } game { count wins { value count percentage streak { min max current } } } segment { type count deaths { sum min max avg } } } }",
        "variables": {"playerId": pid},
    }
    resp = requests.post(url, json=body, headers=headers, timeout=20)
    try:
        data = resp.json()
    except Exception as exc:
        print('parse err', pid, exc)
        continue
    stats = ((data.get('data') or {}).get('playerStatistics')) if isinstance(data, dict) else None
    agg = stats.get('aggregationSeriesIds') if isinstance(stats, dict) else []
    if agg:
        found = {'player_id': pid, 'aggregationSeriesIds': agg, 'series': stats.get('series'), 'game': stats.get('game')}
        break
print(json.dumps({'found': found}, ensure_ascii=False, indent=2))
