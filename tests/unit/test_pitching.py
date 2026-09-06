"""Pitching-staff attribution: who is on the mound, and that it stays labeling only."""

import pytest

from baseball_sim.domain.contracts import PitcherWorkload, PlayerSummary
from baseball_sim.domain.lineup_provider import SyntheticLineupProvider, staff_from_roster
from baseball_sim.sim.match_id import rotation_slot_for
from baseball_sim.sim.pitching import (
    DEFAULT_RELIEVER_OUTS,
    DEFAULT_STARTER_OUTS,
    MAX_STARTER_OUTS,
    MIN_STARTER_OUTS,
    MoundAssignment,
    Pitcher,
    PitchingStaff,
    appearance_outs,
    synthetic_staff,
)
from baseball_sim.sim.state_machine import simulate_game_trace


def staff(*, starter_outs: int = 6, relievers: int = 3) -> PitchingStaff:
    return PitchingStaff(
        rotation=(Pitcher(player_id=1, name="Starter", expected_outs=starter_outs),),
        bullpen=tuple(
            Pitcher(player_id=10 + i, name=f"Reliever {i}", expected_outs=3)
            for i in range(relievers)
        ),
    )


class TestAppearanceLength:
    def test_a_starter_gets_his_own_innings_per_start(self) -> None:
        # 180 innings over 30 starts is six innings a night.
        assert appearance_outs(innings=180.0, role_appearances=30, starter=True) == 18

    def test_a_reliever_is_measured_per_appearance(self) -> None:
        assert appearance_outs(innings=70.0, role_appearances=70, starter=False) == 3

    def test_a_swingman_falls_back_rather_than_reading_as_a_horse(self) -> None:
        """128 innings over 15 starts and 14 relief outings is not an 8-inning starter.

        The season reports one innings total, not one per role, so the ratio is
        unreadable for a pitcher who did both.
        """

        assert (
            appearance_outs(
                innings=128.33, role_appearances=15, total_appearances=29, starter=True
            )
            == DEFAULT_STARTER_OUTS
        )
        # A pure starter is unaffected: his starts are his appearances.
        assert (
            appearance_outs(
                innings=104.0, role_appearances=18, total_appearances=18, starter=True
            )
            == 17
        )

    def test_missing_data_falls_back_to_the_league_shape(self) -> None:
        starter = appearance_outs(innings=None, role_appearances=30, starter=True)
        reliever = appearance_outs(innings=70.0, role_appearances=0, starter=False)
        assert (starter, reliever) == (DEFAULT_STARTER_OUTS, DEFAULT_RELIEVER_OUTS)

    def test_small_samples_are_bounded(self) -> None:
        """An opener with one two-inning start must not become a two-inning starter."""

        assert appearance_outs(innings=2.0, role_appearances=1, starter=True) == MIN_STARTER_OUTS
        assert appearance_outs(innings=90.0, role_appearances=2, starter=True) == MAX_STARTER_OUTS


class TestMoundAssignment:
    def test_the_starter_works_until_his_outs_are_spent(self) -> None:
        mound = MoundAssignment(staff(starter_outs=6))
        assert mound.current is not None and mound.current.name == "Starter"
        mound.record_outs(3)
        assert mound.current.name == "Starter"
        mound.record_outs(3)
        assert mound.current is not None and mound.current.name == "Reliever 0"

    def test_the_bullpen_is_spent_in_order(self) -> None:
        mound = MoundAssignment(staff(starter_outs=3, relievers=2))
        for _ in range(3):
            mound.record_outs(3)
        assert mound.current is not None and mound.current.name == "Reliever 1"

    def test_the_last_arm_finishes_the_game(self) -> None:
        """A game must always be attributed, even in the twentieth inning."""

        mound = MoundAssignment(staff(starter_outs=3, relievers=1))
        for _ in range(20):
            mound.record_outs(3)
        assert mound.current is not None and mound.current.name == "Reliever 0"

    def test_no_staff_attributes_nothing_rather_than_failing(self) -> None:
        mound = MoundAssignment(None)
        mound.record_outs(3)
        assert mound.current is None

    def test_the_rotation_slot_picks_the_starter(self) -> None:
        rotation = tuple(
            Pitcher(player_id=i, name=f"SP{i}", expected_outs=18) for i in range(1, 6)
        )
        full = PitchingStaff(rotation=rotation, bullpen=())
        names = [
            MoundAssignment(full, rotation_slot=slot).current for slot in range(6)
        ]
        assert [pitcher.name for pitcher in names if pitcher] == [
            "SP1", "SP2", "SP3", "SP4", "SP5", "SP1",
        ]


class TestAttributionIsLabelingOnly:
    """The whole point of the seam: naming the pitcher must not move the game."""

    def test_supplying_a_staff_does_not_change_the_simulated_game(self) -> None:
        without = simulate_game_trace(
            seed=42, home_team_id=147, away_team_id=121, scheduled_innings=9
        )
        with_staff = simulate_game_trace(
            seed=42,
            home_team_id=147,
            away_team_id=121,
            scheduled_innings=9,
            home_staff=staff(starter_outs=3, relievers=8),
            away_staff=staff(starter_outs=27, relievers=0),
            rotation_slot=3,
        )
        assert without.result == with_staff.result
        assert [play.event for play in without.plays] == [
            play.event for play in with_staff.plays
        ]

    def test_every_play_names_the_pitcher_who_threw_it(self) -> None:
        trace = simulate_game_trace(
            seed=7, home_team_id=147, away_team_id=121, scheduled_innings=9
        )
        assert all(play.pitcher_id is not None for play in trace.plays)
        # The home staff pitches to the away club and vice versa.
        home_arms = {play.pitcher_id for play in trace.plays if play.fielding_team_id == 147}
        away_arms = {play.pitcher_id for play in trace.plays if play.fielding_team_id == 121}
        assert home_arms and away_arms and not (home_arms & away_arms)

    def test_a_starter_is_relieved_over_a_full_game(self) -> None:
        trace = simulate_game_trace(
            seed=7, home_team_id=147, away_team_id=121, scheduled_innings=9
        )
        used = [play.pitcher_id for play in trace.plays if play.fielding_team_id == 147]
        assert len(set(used)) > 1, "a 16-out starter cannot cover nine innings"
        # A pitcher never returns after being relieved.
        first_seen = [
            player_id
            for index, player_id in enumerate(used)
            if player_id not in used[:index]
        ]
        assert used == sorted(used, key=first_seen.index)

    def test_the_pitcher_of_record_is_the_one_who_threw_the_play(self) -> None:
        """The out that ends an outing belongs to the pitcher who recorded it."""

        mound = MoundAssignment(staff(starter_outs=1))
        pitcher = mound.current
        mound.record_outs(1)
        assert pitcher is not None and pitcher.name == "Starter"
        assert mound.current is not None and mound.current.name == "Reliever 0"

    def test_the_engine_credits_the_out_that_ends_an_outing_to_the_starter(self) -> None:
        """Regression guard: reading the mound after the play misattributes it.

        A starter pulled on the out he just recorded would have that out charged to
        the reliever who had not thrown a pitch yet.
        """

        trace = simulate_game_trace(
            seed=7,
            home_team_id=147,
            away_team_id=121,
            scheduled_innings=9,
            # One out and he is gone, so the very first out is the hand-off.
            home_staff=staff(starter_outs=1, relievers=8),
        )
        home_plays = [play for play in trace.plays if play.fielding_team_id == 147]
        first_out = next(play for play in home_plays if play.outs_after > play.outs_before)
        assert first_out.pitcher_name == "Starter"
        following = home_plays[home_plays.index(first_out) + 1]
        assert following.pitcher_name == "Reliever 0"


class TestStaffFromRoster:
    def roster(self, pitchers: int) -> list[PlayerSummary]:
        return [
            PlayerSummary(player_id=100 + i, full_name=f"Arm {i:02d}", primary_position="P")
            for i in range(pitchers)
        ] + [PlayerSummary(player_id=1, full_name="Slugger", primary_position="RF")]

    def test_the_rotation_is_the_arms_with_the_most_starts(self) -> None:
        roster = self.roster(9)
        workloads = {
            100 + i: PitcherWorkload(innings=180.0, appearances=30, games_started=30 - i)
            for i in range(9)
        }
        built = staff_from_roster(
            roster,
            team_id=147,
            seed=1,
            fallback=SyntheticLineupProvider(),
            workloads=workloads,
        )
        assert [arm.player_id for arm in built.rotation] == [100, 101, 102, 103, 104]
        assert {arm.player_id for arm in built.bullpen} == {105, 106, 107, 108}

    def test_the_best_reliever_pitches_last(self) -> None:
        roster = self.roster(7)
        workloads = {
            105: PitcherWorkload(innings=70.0, appearances=70, games_started=0, fip=2.10),
            106: PitcherWorkload(innings=70.0, appearances=70, games_started=0, fip=5.40),
        }
        built = staff_from_roster(
            roster, team_id=147, seed=1, fallback=SyntheticLineupProvider(), workloads=workloads
        )
        assert [arm.player_id for arm in built.bullpen] == [106, 105]

    def test_a_thin_staff_falls_back_rather_than_fielding_two_arms(self) -> None:
        built = staff_from_roster(
            self.roster(3), team_id=147, seed=1, fallback=SyntheticLineupProvider()
        )
        assert built == synthetic_staff(seed=1, team_id=147)

    def test_outing_length_comes_from_each_pitcher(self) -> None:
        roster = self.roster(6)
        workloads = {
            100: PitcherWorkload(innings=210.0, appearances=30, games_started=30),
            101: PitcherWorkload(innings=120.0, appearances=25, games_started=25),
        }
        built = staff_from_roster(
            roster, team_id=147, seed=1, fallback=SyntheticLineupProvider(), workloads=workloads
        )
        by_id = {arm.player_id: arm.expected_outs for arm in built.rotation}
        assert by_id[100] == 21  # seven innings a start
        assert by_id[101] == 14  # a shade under five


def test_the_rotation_slot_is_stable_for_a_match() -> None:
    assert rotation_slot_for("match_00000000000000ff") == 255
    assert rotation_slot_for("match_deadbeef") == rotation_slot_for("match_deadbeef")


def test_an_unparseable_match_id_still_yields_a_slot() -> None:
    assert rotation_slot_for("not-a-match-id") == 0


@pytest.mark.parametrize("team_id", [147, 121])
def test_the_synthetic_staff_is_reproducible(team_id: int) -> None:
    assert synthetic_staff(seed=5, team_id=team_id) == synthetic_staff(seed=5, team_id=team_id)
    assert synthetic_staff(seed=5, team_id=team_id) != synthetic_staff(seed=6, team_id=team_id)
