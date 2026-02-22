from baseball_sim.seeders.roster import generate_seeded_team_roster


def test_seeded_roster_is_deterministic() -> None:
    first = generate_seeded_team_roster(team_id=147, seed=555)
    second = generate_seeded_team_roster(team_id=147, seed=555)

    assert first == second
    assert len(first.lineup) == 9
    assert set(first.fielders.keys()) == {"P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"}


def test_seeded_roster_changes_with_seed() -> None:
    first = generate_seeded_team_roster(team_id=147, seed=555)
    second = generate_seeded_team_roster(team_id=147, seed=556)
    assert first != second
