from baseball_sim.sim.match_id import create_match_id


def test_match_id_is_deterministic() -> None:
    first = create_match_id(
        seed=1234,
        model_version="baseline-v1",
        data_snapshot_id="snapshot-1",
        home_team_id=147,
        away_team_id=121,
        scheduled_innings=9,
        ruleset_id="rules-v1",
        ruleset_checksum="abc123",
    )
    second = create_match_id(
        seed=1234,
        model_version="baseline-v1",
        data_snapshot_id="snapshot-1",
        home_team_id=147,
        away_team_id=121,
        scheduled_innings=9,
        ruleset_id="rules-v1",
        ruleset_checksum="abc123",
    )
    assert first == second


def test_match_id_changes_with_seed() -> None:
    first = create_match_id(
        seed=1234,
        model_version="baseline-v1",
        data_snapshot_id="snapshot-1",
        home_team_id=147,
        away_team_id=121,
        scheduled_innings=9,
        ruleset_id="rules-v1",
        ruleset_checksum="abc123",
    )
    second = create_match_id(
        seed=1235,
        model_version="baseline-v1",
        data_snapshot_id="snapshot-1",
        home_team_id=147,
        away_team_id=121,
        scheduled_innings=9,
        ruleset_id="rules-v1",
        ruleset_checksum="abc123",
    )
    assert first != second
