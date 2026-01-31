from typing import Dict, Any, List
from .client import GridClient


class GridFetcher:
    def __init__(self, client: GridClient):
        self.client = client

    def fetch_series(self, series_id: str) -> Dict[str, Any]:
        """Fetch minimal series info (finished match)."""
        query = """
        query GetSeries($id: ID!) {
          series(id: $id) {
            id
            format { name }
            startTimeScheduled
            teams { baseInfo { name } }
          }
        }
        """
        return self.client.run_query(query, {"id": series_id})

    def fetch_player_stats(self, player_id: str) -> Dict[str, Any]:
        query = """
        query PlayerStats($id: ID!) {
          playerStatistics(playerId: $id, filter: {}) {
            game { count }
            series { count }
          }
        }
        """
        return self.client.run_query(query, {"id": player_id})

    def fetch_games(self, series_id: str) -> List[Dict[str, Any]]:
        """Fetch games under a series. Best-effort GraphQL shape with tolerant fields."""
        query = """
        query SeriesGames($id: ID!) {
          series(id: $id) {
            id
            games {
              id
              status
              map { name }
              teams {
                team { id name }
                score
                side
              }
            }
          }
        }
        """
        payload = self.client.run_query(query, {"id": series_id})
        series = payload.get("data", {}).get("series") or {}
        games = series.get("games") or []
        return games

    def fetch_game_timeline(self, game_id: str) -> Dict[str, Any]:
        """
        Fetch timeline / rounds for a single game. The shape may differ by GRID deployment;
        we keep field access tolerant and let mapping layer handle missing parts.
        """
        query = """
        query GameTimeline($id: ID!) {
          game(id: $id) {
            id
            map { name }
            rounds {
              number
              winner { name id }
              teams {
                team { id name }
                side
                score
                economy { credits }
              }
              events {
                type
                time
                player { id name }
                victim { id name }
                isTrade
              }
            }
          }
        }
        """
        payload = self.client.run_query(query, {"id": game_id})
        return payload.get("data", {}).get("game") or {}
