import httpx
import pytest

from baseball_sim.ingest.mlb_stats_client import MLBStatsClient


@pytest.mark.asyncio
async def test_get_teams_returns_team_objects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/teams"
        return httpx.Response(
            status_code=200,
            json={
                "teams": [
                    {"id": 147, "name": "Yankees"},
                    {"id": 121, "name": "Mets"},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://statsapi.mlb.com/api/v1", transport=transport
    ) as client:
        stats_client = MLBStatsClient(
            base_url="https://statsapi.mlb.com/api/v1",
            timeout_seconds=10.0,
            client=client,
        )
        teams = await stats_client.get_teams()

    assert teams[0]["id"] == 147
    assert teams[1]["name"] == "Mets"


@pytest.mark.asyncio
async def test_retry_on_transient_http_status_then_succeeds() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(status_code=503, json={"error": "temporary"})
        return httpx.Response(status_code=200, json={"teams": [{"id": 147, "name": "Yankees"}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://statsapi.mlb.com/api/v1", transport=transport
    ) as client:
        stats_client = MLBStatsClient(
            base_url="https://statsapi.mlb.com/api/v1",
            timeout_seconds=10.0,
            max_attempts=2,
            backoff_seconds=0.0,
            client=client,
        )
        teams = await stats_client.get_teams()

    assert attempts == 2
    assert teams[0]["id"] == 147


@pytest.mark.asyncio
async def test_no_retry_for_non_retryable_status() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status_code=404, json={"message": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://statsapi.mlb.com/api/v1", transport=transport
    ) as client:
        stats_client = MLBStatsClient(
            base_url="https://statsapi.mlb.com/api/v1",
            timeout_seconds=10.0,
            max_attempts=3,
            backoff_seconds=0.0,
            client=client,
        )
        with pytest.raises(httpx.HTTPStatusError):
            await stats_client.get_teams()

    assert attempts == 1


@pytest.mark.asyncio
async def test_get_team_roster_returns_roster_entries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/teams/147/roster"
        return httpx.Response(
            status_code=200,
            json={
                "roster": [
                    {"person": {"id": 592450, "fullName": "Aaron Judge"}},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://statsapi.mlb.com/api/v1", transport=transport
    ) as client:
        stats_client = MLBStatsClient(
            base_url="https://statsapi.mlb.com/api/v1",
            timeout_seconds=10.0,
            client=client,
        )
        roster = await stats_client.get_team_roster(team_id=147)

    assert roster[0]["person"]["id"] == 592450
