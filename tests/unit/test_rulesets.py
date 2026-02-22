import json
from pathlib import Path

import pytest

from baseball_sim.sim.rulesets import load_ruleset_from_path


def test_load_ruleset_from_path(tmp_path: Path) -> None:
    ruleset_path = tmp_path / "ruleset.json"
    ruleset_path.write_text(
        json.dumps(
            {
                "ruleset_id": "test_rules_v1",
                "scheduled_innings": 9,
                "max_innings": 12,
                "max_plate_appearances_per_half": 60,
                "skip_home_bottom_if_leading_after_top_final": True,
                "enable_walkoff": True,
                "enable_runner_on_second_in_extras": True,
                "runner_on_second_start_inning": 10,
                "home_field_event_boost": 0.01,
            }
        ),
        encoding="utf-8",
    )

    loaded = load_ruleset_from_path(ruleset_path.as_posix())

    assert loaded.ruleset.ruleset_id == "test_rules_v1"
    assert loaded.ruleset.max_innings == 12
    assert len(loaded.checksum_sha256) == 64


def test_ruleset_validation_rejects_high_max_innings(tmp_path: Path) -> None:
    ruleset_path = tmp_path / "bad_ruleset.json"
    ruleset_path.write_text(
        json.dumps(
            {
                "ruleset_id": "bad_rules",
                "scheduled_innings": 9,
                "max_innings": 25,
                "max_plate_appearances_per_half": 60,
                "skip_home_bottom_if_leading_after_top_final": True,
                "enable_walkoff": True,
                "enable_runner_on_second_in_extras": False,
                "runner_on_second_start_inning": 10,
                "home_field_event_boost": 0.01,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_ruleset_from_path(ruleset_path.as_posix())
