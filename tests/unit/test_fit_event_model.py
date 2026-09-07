"""Fitting the event model: what the knobs are allowed to move, and what they are not."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from baseball_sim.eval.fit_event_model import scaled_model
from baseball_sim.sim.profiles import TeamProfile
from baseball_sim.sim.rulesets import (
    DEFAULT_EVENT_MODEL,
    DEFAULT_RULESET,
    load_ruleset_from_path,
    parse_ruleset,
)
from baseball_sim.sim.season import ScheduledGame, simulate_season

RATE_NAMES = ("out", "walk", "single", "double", "triple", "home_run")


class TestScaling:
    def test_scaling_leaves_the_league_average_alone(self) -> None:
        """Only the gap between clubs should narrow, not what an average game looks
        like — otherwise fitting the spread would move the run environment with it."""

        scaled = scaled_model(DEFAULT_EVENT_MODEL, sensitivity=0.5, out_base_shift=0.0)
        for name in RATE_NAMES:
            assert getattr(scaled, name).base == getattr(DEFAULT_EVENT_MODEL, name).base

    def test_scaling_shrinks_every_sensitivity_by_the_same_factor(self) -> None:
        scaled = scaled_model(DEFAULT_EVENT_MODEL, sensitivity=0.5, out_base_shift=0.0)
        for name in RATE_NAMES:
            assert getattr(scaled, name).sensitivity == pytest.approx(
                getattr(DEFAULT_EVENT_MODEL, name).sensitivity * 0.5
            )

    def test_the_bounds_shrink_with_the_sensitivity(self) -> None:
        """A clamp sized for the old sensitivity would bite in the wrong place under
        the new one, quietly undoing part of the fit at the extremes."""

        scaled = scaled_model(DEFAULT_EVENT_MODEL, sensitivity=0.5, out_base_shift=0.0)
        original = DEFAULT_EVENT_MODEL.out
        assert scaled.out.maximum - scaled.out.base == pytest.approx(
            (original.maximum - original.base) * 0.5
        )
        assert scaled.out.base - scaled.out.minimum == pytest.approx(
            (original.base - original.minimum) * 0.5
        )

    def test_the_shift_moves_only_the_out_rate(self) -> None:
        scaled = scaled_model(DEFAULT_EVENT_MODEL, sensitivity=1.0, out_base_shift=-0.02)
        assert scaled.out.base == pytest.approx(DEFAULT_EVENT_MODEL.out.base - 0.02)
        for name in ("walk", "single", "double", "triple", "home_run"):
            assert getattr(scaled, name).base == getattr(DEFAULT_EVENT_MODEL, name).base

    def test_the_identity_scaling_changes_nothing(self) -> None:
        assert scaled_model(
            DEFAULT_EVENT_MODEL, sensitivity=1.0, out_base_shift=0.0
        ) == DEFAULT_EVENT_MODEL

    def test_the_scaled_model_stays_valid(self) -> None:
        """Bases must stay inside their own bounds, or the ruleset is unloadable."""

        for sensitivity in (1.0, 0.7, 0.3):
            scaled = scaled_model(
                DEFAULT_EVENT_MODEL, sensitivity=sensitivity, out_base_shift=-0.02
            )
            for name in RATE_NAMES:
                rates = getattr(scaled, name)
                assert rates.minimum <= rates.base <= rates.maximum


class TestFittedRuleset:
    def test_the_shipped_fitted_ruleset_loads_and_validates(self) -> None:
        loaded = load_ruleset_from_path("rulesets/mlb_2026_fitted.json")
        assert loaded.ruleset.ruleset_id == "mlb_2026_fitted_v1"
        assert loaded.checksum_sha256

    def test_it_round_trips_through_the_parser(self) -> None:
        payload = json.loads(Path("rulesets/mlb_2026_fitted.json").read_text())
        assert parse_ruleset(payload).event_model == load_ruleset_from_path(
            "rulesets/mlb_2026_fitted.json"
        ).ruleset.event_model

    def test_the_unfitted_ruleset_is_kept_so_its_runs_stay_reproducible(self) -> None:
        loaded = load_ruleset_from_path("rulesets/mlb_2026_regular.json")
        assert loaded.ruleset.event_model == DEFAULT_EVENT_MODEL


def test_the_fitted_model_finishes_clubs_closer_together() -> None:
    """The whole point of the fit, asserted on behaviour rather than on constants."""

    strong = TeamProfile(0.9, 0.8, 0.9, 0.6, 0.9, 0.8, 0.7)
    weak = TeamProfile(0.1, 0.2, 0.1, 0.4, 0.1, 0.2, 0.3)
    schedule = [
        ScheduledGame(game_pk=800_000 + i, home_team_id=147, away_team_id=121)
        for i in range(120)
    ]
    profiles = {147: strong, 121: weak}

    unfitted = simulate_season(
        seed=4, schedule=schedule, profiles=profiles, ruleset=DEFAULT_RULESET
    )
    fitted = simulate_season(
        seed=4,
        schedule=schedule,
        profiles=profiles,
        ruleset=replace(
            DEFAULT_RULESET,
            event_model=scaled_model(
                DEFAULT_EVENT_MODEL, sensitivity=0.7, out_base_shift=-0.020
            ),
        ),
    )
    assert fitted.standings[0].win_percentage < unfitted.standings[0].win_percentage
