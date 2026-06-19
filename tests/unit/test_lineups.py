from baseball_sim.domain.contracts import DeterministicContext, PlayerSummary, SimulateGameRequest
from baseball_sim.domain.lineup_provider import (
    SyntheticLineupProvider,
    lineup_from_roster,
)
from baseball_sim.domain.service import simulate_game_play_by_play
from baseball_sim.sim.lineups import synthetic_lineup


def test_synthetic_lineup_has_nine_named_batters() -> None:
    lineup = synthetic_lineup(seed=1234, team_id=147)
    assert len(lineup) == 9
    assert all(batter.name for batter in lineup)
    # Deterministic for a given seed + team.
    assert synthetic_lineup(seed=1234, team_id=147) == lineup


def test_synthetic_lineup_provider_matches_helper() -> None:
    provider = SyntheticLineupProvider()
    assert provider.lineup(team_id=147, seed=1234) == synthetic_lineup(seed=1234, team_id=147)


def test_lineup_from_roster_uses_real_position_players() -> None:
    roster = [
        PlayerSummary(player_id=i, full_name=f"Player {i}", primary_position="OF")
        for i in range(1, 10)
    ]
    roster.append(PlayerSummary(player_id=99, full_name="Ace", primary_position="P"))

    lineup = lineup_from_roster(
        roster, team_id=147, seed=1234, fallback=SyntheticLineupProvider()
    )
    assert len(lineup) == 9
    assert all(batter.player_id != 99 for batter in lineup)  # pitcher excluded
    assert lineup[0].name == "Player 1"


def test_lineup_from_roster_falls_back_when_too_few() -> None:
    roster = [PlayerSummary(player_id=1, full_name="Solo", primary_position="1B")]
    lineup = lineup_from_roster(
        roster, team_id=147, seed=1234, fallback=SyntheticLineupProvider()
    )
    assert lineup == synthetic_lineup(seed=1234, team_id=147)


def _request() -> SimulateGameRequest:
    return SimulateGameRequest(
        home_team_id=147,
        away_team_id=121,
        innings=9,
        context=DeterministicContext(
            seed=1234, model_version="baseline-v1", data_snapshot_id="t"
        ),
    )


def test_play_by_play_attributes_batters_in_order() -> None:
    result = simulate_game_play_by_play(_request())
    away = synthetic_lineup(seed=1234, team_id=121)

    # The first three top-of-1st plate appearances follow the away lineup order.
    top_plays = [p for p in result.plays if p.half == "top" and p.event != "tiebreaker"]
    assert top_plays[0].batter_name == away[0].name
    assert top_plays[1].batter_name == away[1].name
    assert top_plays[2].batter_name == away[2].name


def test_play_by_play_attribution_is_deterministic() -> None:
    first = simulate_game_play_by_play(_request())
    second = simulate_game_play_by_play(_request())
    assert [p.batter_id for p in first.plays] == [p.batter_id for p in second.plays]
