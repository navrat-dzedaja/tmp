"""Client for the football-data.org REST API (v4)."""
from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.football-data.org/v4"


class FootballDataClient:
    def __init__(self, api_token: str | None):
        self._token = api_token
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"X-Auth-Token": api_token or ""},
            timeout=15.0,
        )

    def _get(self, path: str, params: dict | None = None) -> dict | None:
        if not self._token:
            logger.warning("FOOTBALL_DATA_API_TOKEN not set - skipping football-data.org request %s", path)
            return None
        try:
            resp = self._client.get(path, params=params or {})
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("football-data.org request failed: %s %s", path, params)
            return None

    def upcoming_matches(self, competition_code: str, lookahead_days: int) -> list[dict]:
        """Scheduled matches for a competition within the lookahead window."""
        today = date.today()
        params = {
            "dateFrom": today.isoformat(),
            "dateTo": (today + timedelta(days=lookahead_days)).isoformat(),
            "status": "SCHEDULED",
        }
        data = self._get(f"/competitions/{competition_code}/matches", params=params)
        if not data:
            return []
        return data.get("matches", [])

    def standings(self, competition_code: str) -> list[dict]:
        """Flat league table (TOTAL type) as a list of {position, team, points, ...}."""
        data = self._get(f"/competitions/{competition_code}/standings")
        if not data:
            return []
        for table in data.get("standings", []):
            if table.get("type") == "TOTAL":
                return table.get("table", [])
        return []

    def recent_form(self, team_id: int, limit: int = 5) -> list[dict]:
        """Last `limit` finished matches for a team, most recent first."""
        params = {"status": "FINISHED", "limit": limit}
        data = self._get(f"/teams/{team_id}/matches", params=params)
        if not data:
            return []
        matches = data.get("matches", [])
        return sorted(matches, key=lambda m: m.get("utcDate", ""), reverse=True)[:limit]

    def head_to_head(self, match_id: int, limit: int = 5) -> list[dict]:
        data = self._get(f"/matches/{match_id}/head2head", params={"limit": limit})
        if not data:
            return []
        return data.get("matches", [])

    def close(self) -> None:
        self._client.close()
