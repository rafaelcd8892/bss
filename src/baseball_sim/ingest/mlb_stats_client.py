import asyncio
from collections.abc import Mapping
from typing import Any

import httpx

from baseball_sim.config import Settings, get_settings


class MLBStatsClient:
    """Thin async wrapper around MLB Stats API endpoints."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        max_attempts: int = 3,
        backoff_seconds: float = 0.25,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must be >= 0")

        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._retry_status_codes = {408, 425, 429, 500, 502, 503, 504}
        self._owned_client = client is None
        if client is not None:
            self._client = client
            return
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)

    async def __aenter__(self) -> "MLBStatsClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owned_client:
            await self._client.aclose()

    async def _get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._client.get(path, params=params)
                if (
                    response.status_code in self._retry_status_codes
                    and attempt < self._max_attempts
                ):
                    await self._sleep_backoff(attempt)
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Expected JSON object payload from MLB Stats API")
                return payload
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt >= self._max_attempts:
                    raise RuntimeError(
                        f"MLB Stats API request failed after {self._max_attempts} attempts: {path}"
                    ) from exc
                await self._sleep_backoff(attempt)
            except httpx.HTTPStatusError as exc:
                if (
                    attempt >= self._max_attempts
                    or exc.response.status_code not in self._retry_status_codes
                ):
                    raise
                await self._sleep_backoff(attempt)

        raise RuntimeError("MLB Stats API request retry loop exhausted unexpectedly")

    async def _sleep_backoff(self, attempt: int) -> None:
        delay_seconds = self._backoff_seconds * (2 ** (attempt - 1))
        if delay_seconds <= 0:
            return
        await asyncio.sleep(delay_seconds)

    async def get_teams(
        self, *, sport_id: int = 1, season: int | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {"sportId": sport_id}
        if season is not None:
            params["season"] = season
        payload = await self._get_json("/teams", params=params)
        teams = payload.get("teams", [])
        if not isinstance(teams, list):
            raise ValueError("Expected teams array from MLB Stats API")
        return [team for team in teams if isinstance(team, dict)]

    async def get_player(self, *, player_id: int) -> dict[str, Any]:
        payload = await self._get_json(f"/people/{player_id}")
        people = payload.get("people", [])
        if not isinstance(people, list) or not people:
            raise ValueError(f"No player found for player_id={player_id}")
        person = people[0]
        if not isinstance(person, dict):
            raise ValueError(f"Invalid player payload for player_id={player_id}")
        return person

    async def get_schedule(
        self,
        *,
        start_date: str,
        end_date: str,
        sport_id: int = 1,
    ) -> list[dict[str, Any]]:
        payload = await self._get_json(
            "/schedule",
            params={
                "sportId": sport_id,
                "startDate": start_date,
                "endDate": end_date,
            },
        )
        dates = payload.get("dates", [])
        if not isinstance(dates, list):
            raise ValueError("Expected dates array from MLB Stats API schedule endpoint")
        return [entry for entry in dates if isinstance(entry, dict)]

    async def get_team_roster(
        self,
        *,
        team_id: int,
        roster_type: str = "active",
    ) -> list[dict[str, Any]]:
        payload = await self._get_json(
            f"/teams/{team_id}/roster", params={"rosterType": roster_type}
        )
        roster = payload.get("roster", [])
        if not isinstance(roster, list):
            raise ValueError(f"Expected roster array for team_id={team_id}")
        return [entry for entry in roster if isinstance(entry, dict)]


def create_default_mlb_stats_client(settings: Settings | None = None) -> MLBStatsClient:
    app_settings = settings if settings is not None else get_settings()
    return MLBStatsClient(
        base_url=app_settings.mlb_stats_api_base_url,
        timeout_seconds=app_settings.mlb_stats_timeout_seconds,
        max_attempts=app_settings.mlb_stats_max_attempts,
        backoff_seconds=app_settings.mlb_stats_backoff_seconds,
    )
