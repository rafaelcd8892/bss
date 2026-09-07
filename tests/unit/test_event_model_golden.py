"""The engine's output must not move except when the event model deliberately does.

These are recorded outputs from before the tuning constants were lifted out of the
state machine and into the ruleset. The refactor was meant to change where the numbers
live, not what they produce; this is what makes that claim checkable rather than
asserted. When the model is deliberately retuned, the new constants belong in a new
ruleset — not in an edit to this file.
"""

import json
from pathlib import Path

from baseball_sim.sim.profiles import TeamProfile
from baseball_sim.sim.state_machine import simulate_game_trace

GOLDEN = json.loads(
    (Path(__file__).parent.parent / "data" / "event_model_golden.json").read_text()
)

CASES = {
    "even": (
        TeamProfile(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
        TeamProfile(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    ),
    "strong": (
        TeamProfile(0.9, 0.8, 0.9, 0.6, 0.9, 0.8, 0.7),
        TeamProfile(0.1, 0.2, 0.1, 0.4, 0.1, 0.2, 0.3),
    ),
    "weak": (
        TeamProfile(0.1, 0.2, 0.1, 0.4, 0.1, 0.2, 0.3),
        TeamProfile(0.9, 0.8, 0.9, 0.6, 0.9, 0.8, 0.7),
    ),
    # Both extremes, so a clamp that moves is caught rather than silently absorbed.
    "edge": (
        TeamProfile(1, 1, 1, 1, 1, 1, 1),
        TeamProfile(0, 0, 0, 0, 0, 0, 0),
    ),
}


def test_the_default_event_model_reproduces_recorded_games() -> None:
    for name, (home, away) in CASES.items():
        for seed, expected in enumerate(GOLDEN[name]):
            trace = simulate_game_trace(
                seed=seed,
                home_team_id=147,
                away_team_id=121,
                scheduled_innings=9,
                home_profile=home,
                away_profile=away,
            )
            actual = [
                trace.result.home_score,
                trace.result.away_score,
                trace.result.innings_played,
                len(trace.plays),
                "".join(play.event[0] for play in trace.plays[:40]),
            ]
            assert actual == expected, f"{name} seed={seed} moved"
