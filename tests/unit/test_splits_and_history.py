"""Per-team splits and career history.

A season is not one row per player. A traded player has a line with each club plus a
season total whose team is null, and the two answer different questions: a club's
profile wants his line *with that club*, a leaderboard and a player rating want his
year. Keeping only one of them was the bug this covers.
"""

from typing import Any

import pytest

from baseball_sim.domain.postgres_stats import build_stat_line_provider_from_rows
from baseball_sim.ingest.pipeline import stat_requests_for
from baseball_sim.ingest.stats import (
    normalize_player_fielding,
    normalize_player_stats,
)


def split(*, season: str, team_id: int | None, pa: int, hits: int) -> dict[str, Any]:
    stat: dict[str, Any] = {
        "plateAppearances": pa,
        "atBats": pa - 10,
        "hits": hits,
        "doubles": 10,
        "triples": 1,
        "homeRuns": 8,
        "baseOnBalls": 10,
        "strikeOuts": 20,
    }
    payload: dict[str, Any] = {"season": season, "stat": stat}
    if team_id is not None:
        payload["team"] = {"id": team_id}
    return payload


def hitting_payload(splits: list[dict[str, Any]]) -> dict[str, Any]:
    return {"stats": [{"group": {"displayName": "hitting"}, "splits": splits}]}


TRADED = hitting_payload(
    [
        # The API leads with the season total, whose team is null.
        split(season="2022", team_id=None, pa=664, hits=170),
        split(season="2022", team_id=120, pa=436, hits=110),
        split(season="2022", team_id=135, pa=228, hits=60),
    ]
)


class TestSplits:
    def test_every_split_is_kept_not_just_the_first(self) -> None:
        records = normalize_player_stats(player_id=1, season=2022, payload=TRADED)
        assert len(records) == 3
        assert sorted(r.team_id for r in records if r.team_id) == [120, 135]

    def test_the_season_total_is_kept_and_marked_by_a_null_team(self) -> None:
        records = normalize_player_stats(player_id=1, season=2022, payload=TRADED)
        [total] = [r for r in records if r.team_id is None]
        assert total.pa == 664

    def test_a_player_who_was_never_traded_has_one_split(self) -> None:
        payload = hitting_payload([split(season="2026", team_id=147, pa=600, hits=150)])
        [record] = normalize_player_stats(player_id=1, season=2026, payload=payload)
        assert record.team_id == 147


class TestHistory:
    def test_each_split_carries_its_own_season(self) -> None:
        """One request returns a career; stamping it with the requested season would
        collapse a decade of lines onto one year."""

        payload = hitting_payload(
            [
                split(season="2019", team_id=147, pa=500, hits=130),
                split(season="2020", team_id=147, pa=200, hits=55),
                split(season="2021", team_id=121, pa=600, hits=160),
            ]
        )
        records = normalize_player_stats(player_id=1, season=2026, payload=payload)
        assert sorted(r.season for r in records) == [2019, 2020, 2021]

    def test_an_unparseable_season_falls_back_to_the_requested_one(self) -> None:
        payload = hitting_payload([{"season": "n/a", "stat": {"atBats": 1, "hits": 1}}])
        [record] = normalize_player_stats(player_id=1, season=2026, payload=payload)
        assert record.season == 2026

    def test_history_swaps_the_counting_request_but_not_the_expected_one(self) -> None:
        requests = stat_requests_for("RF", fetch_all=False, history=True)
        assert ("hitting", "yearByYear") in requests
        assert ("fielding", "yearByYear") in requests
        # Expected stats have no year-by-year view, so they stay on the season.
        assert ("hitting", "expectedStatistics") in requests

    def test_without_history_the_counting_request_is_one_season(self) -> None:
        requests = stat_requests_for("RF", fetch_all=False, history=False)
        assert all(stat_type != "yearByYear" for _, stat_type in requests)


# player_id, team_id, stat_group, ip, at_bats, singles, doubles, triples, home_runs,
# walks, intentional_walks, hit_by_pitch, sacrifice_flies, strikeouts, stolen_bases,
# pa, xwoba
def row(team_id: int | None, pa: int, singles: int) -> tuple[Any, ...]:
    return (
        7, team_id, "hitting", None, pa - 40, singles, 10, 1, 8, 30, 2, 3, 2, 90, 5,
        pa, None,
    )


class TestServingReadsTheRightSplit:
    def test_a_club_profile_uses_the_line_with_that_club(self) -> None:
        provider = build_stat_line_provider_from_rows(
            rows=[row(None, 664, 150), row(120, 436, 100), row(135, 228, 50)]
        )
        washington = provider.team_profile(team_id=120, seed=1)
        san_diego = provider.team_profile(team_id=135, seed=1)
        # Both clubs get a profile from him, which is the whole point: before per-team
        # splits his line had no team and counted for neither.
        assert washington is not None and san_diego is not None
        assert washington != san_diego

    def test_a_player_rating_uses_the_season_total(self) -> None:
        traded = build_stat_line_provider_from_rows(
            rows=[row(None, 664, 150), row(120, 436, 100), row(135, 228, 50)]
        )
        total_only = build_stat_line_provider_from_rows(rows=[row(None, 664, 150)])
        assert (
            traded.player_rating(player_id=7, seed=1).metrics["woba"]
            == total_only.player_rating(player_id=7, seed=1).metrics["woba"]
        )

    def test_the_total_wins_whatever_order_the_rows_arrive_in(self) -> None:
        """Row order is the database's business, not a correctness dependency."""

        forwards = build_stat_line_provider_from_rows(
            rows=[row(None, 664, 150), row(120, 436, 100)]
        )
        backwards = build_stat_line_provider_from_rows(
            rows=[row(120, 436, 100), row(None, 664, 150)]
        )
        assert forwards.player_rating(player_id=7, seed=1) == backwards.player_rating(
            player_id=7, seed=1
        )

    def test_a_player_with_no_total_still_gets_a_rating(self) -> None:
        provider = build_stat_line_provider_from_rows(rows=[row(147, 600, 140)])
        rating = provider.player_rating(player_id=7, seed=1)
        assert rating.sources["woba"] == "real"

    def test_a_club_is_not_credited_with_the_season_total(self) -> None:
        """Adding the total to a club would count a traded player's year twice."""

        with_total = build_stat_line_provider_from_rows(
            rows=[row(None, 664, 150), row(120, 436, 100)]
        )
        club_only = build_stat_line_provider_from_rows(rows=[row(120, 436, 100)])
        assert with_total.team_profile(team_id=120, seed=1) == club_only.team_profile(
            team_id=120, seed=1
        )


@pytest.mark.parametrize("payload", [{}, {"stats": None}, {"stats": [{"splits": None}]}])
def test_malformed_payloads_yield_nothing_rather_than_raising(payload: dict) -> None:
    assert normalize_player_stats(player_id=1, season=2026, payload=payload) == []


def fielding_split(*, season: str, position: str, team_id: int, innings: str) -> dict[str, Any]:
    return {
        "season": season,
        "team": {"id": team_id},
        "stat": {
            "position": {"abbreviation": position},
            "innings": innings,
            "putOuts": 120,
            "assists": 200,
            "errors": 8,
            "chances": 328,
            "games": 90,
            "gamesStarted": 88,
        },
    }


def fielding_payload(splits: list[dict[str, Any]]) -> dict[str, Any]:
    return {"stats": [{"group": {"displayName": "fielding"}, "splits": splits}]}


class TestFieldingSplits:
    """A fielder's splits multiply two ways: by position, and by club."""

    def test_a_utility_player_keeps_every_position(self) -> None:
        payload = fielding_payload(
            [
                fielding_split(season="2026", position="SS", team_id=147, innings="700.0"),
                fielding_split(season="2026", position="2B", team_id=147, innings="300.0"),
                fielding_split(season="2026", position="3B", team_id=147, innings="120.0"),
            ]
        )
        records = normalize_player_fielding(player_id=1, season=2026, payload=payload)
        assert sorted(r.line.position for r in records) == ["2B", "3B", "SS"]

    def test_a_traded_fielder_keeps_the_same_position_at_both_clubs(self) -> None:
        payload = fielding_payload(
            [
                fielding_split(season="2026", position="SS", team_id=120, innings="600.0"),
                fielding_split(season="2026", position="SS", team_id=135, innings="400.0"),
            ]
        )
        records = normalize_player_fielding(player_id=1, season=2026, payload=payload)
        assert sorted(r.team_id or 0 for r in records) == [120, 135]

    def test_each_fielding_split_carries_its_own_season(self) -> None:
        payload = fielding_payload(
            [
                fielding_split(season="2024", position="SS", team_id=147, innings="900.0"),
                fielding_split(season="2025", position="SS", team_id=147, innings="950.0"),
            ]
        )
        records = normalize_player_fielding(player_id=1, season=2026, payload=payload)
        assert sorted(r.season for r in records) == [2024, 2025]
