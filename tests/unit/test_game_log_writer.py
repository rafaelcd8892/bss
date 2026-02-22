from pathlib import Path

from baseball_sim.cli.game_log import GameLogWriter, MatchContext
from baseball_sim.sim.state_machine import PlayTrace


def test_game_log_writer_persists_files(tmp_path: Path) -> None:
    context = MatchContext(
        match_id="match_test1",
        seed=1,
        model_version="v1",
        data_snapshot_id="snap-1",
        home_team_id=147,
        away_team_id=121,
        ruleset_id="rules-v1",
        ruleset_checksum="abc123",
        scheduled_innings=9,
    )
    writer = GameLogWriter(log_dir=tmp_path, context=context)
    writer.write_header(extra={"x": 1})
    writer.write_play(
        play=PlayTrace(
            play_index=1,
            inning=1,
            half="top",
            batting_team_id=121,
            fielding_team_id=147,
            event="single",
            outs_before=0,
            outs_after=0,
            bases_before="000",
            bases_after="100",
            runs_scored_on_play=0,
            home_score_after_play=0,
            away_score_after_play=0,
            description="Single to center.",
        )
    )
    writer.write_summary(payload={"home_score": 1, "away_score": 0})

    assert writer.jsonl_path.exists()
    assert writer.summary_path.exists()
    assert (tmp_path / "match_registry.jsonl").exists()
