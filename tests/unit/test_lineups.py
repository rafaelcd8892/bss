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


def _position_players(names: list[str]) -> list[PlayerSummary]:
    return [
        PlayerSummary(player_id=i, full_name=name, primary_position="OF")
        for i, name in enumerate(names, start=1)
    ]


def test_lineup_is_ordered_by_woba_not_alphabetically() -> None:
    # Deliberately alphabetical input so a stable sort alone would not reorder it.
    roster = _position_players(
        ["Abel", "Baker", "Carter", "Dunn", "Evans", "Ford", "Gray", "Hunt", "Irwin"]
    )
    # Irwin is the best hitter, Abel the worst.
    woba = {player.player_id: 0.250 + 0.01 * player.player_id for player in roster}

    lineup = lineup_from_roster(
        roster, team_id=147, seed=1234, fallback=SyntheticLineupProvider(), woba=woba
    )

    assert [batter.name for batter in lineup][:3] == ["Irwin", "Hunt", "Gray"]
    assert lineup[-1].name == "Abel"


def test_players_without_woba_bat_last() -> None:
    roster = _position_players(
        ["Aaron", "Bishop", "Cole", "Drake", "Ellis", "Finch", "Gomez", "Hale", "Ivers"]
    )
    # Only two players have ingested stats; they should lead off regardless of name.
    woba = {8: 0.310, 9: 0.400}

    lineup = lineup_from_roster(
        roster, team_id=147, seed=1234, fallback=SyntheticLineupProvider(), woba=woba
    )

    assert [batter.name for batter in lineup][:2] == ["Ivers", "Hale"]
    # The rest keep a deterministic alphabetical order behind them.
    assert [batter.name for batter in lineup][2:] == [
        "Aaron",
        "Bishop",
        "Cole",
        "Drake",
        "Ellis",
        "Finch",
        "Gomez",
    ]


def test_equal_woba_breaks_on_name_for_determinism() -> None:
    roster = _position_players(
        ["Zeta", "Alpha", "Mike", "Nora", "Owen", "Pace", "Quinn", "Ruiz", "Sato"]
    )
    woba = {player.player_id: 0.330 for player in roster}

    first = lineup_from_roster(
        roster, team_id=147, seed=1234, fallback=SyntheticLineupProvider(), woba=woba
    )
    second = lineup_from_roster(
        list(reversed(roster)),
        team_id=147,
        seed=1234,
        fallback=SyntheticLineupProvider(),
        woba=woba,
    )

    assert first == second
    assert first[0].name == "Alpha"


def test_woba_ordering_still_excludes_pitchers() -> None:
    roster = _position_players(["A", "B", "C", "D", "E", "F", "G", "H", "I"])
    ace = PlayerSummary(player_id=99, full_name="Ace", primary_position="P")
    roster.append(ace)
    woba = {99: 0.500}  # even an elite-hitting pitcher stays out of the lineup

    lineup = lineup_from_roster(
        roster, team_id=147, seed=1234, fallback=SyntheticLineupProvider(), woba=woba
    )

    assert all(batter.player_id != 99 for batter in lineup)
    assert len(lineup) == 9
