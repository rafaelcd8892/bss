from __future__ import annotations

import argparse
import asyncio
import json
import select
import sys
import time

from baseball_sim.config import get_settings
from baseball_sim.seeders.roster import SeededTeamRoster
from baseball_sim.sim.match_id import create_match_id
from baseball_sim.sim.rulesets import load_ruleset_from_path
from baseball_sim.sim.state_machine import GameSimulationTrace, PlayTrace, simulate_game_trace

from .game_log import GameLogWriter, MatchContext
from .roster_loader import load_watch_rosters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch a deterministic baseball simulation in terminal."
    )
    parser.add_argument("--home-team-id", type=int, required=True)
    parser.add_argument("--away-team-id", type=int, required=True)
    parser.add_argument("--home-team-name", type=str, default=None)
    parser.add_argument("--away-team-name", type=str, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--innings", type=int, default=None)
    parser.add_argument("--delay-seconds", type=float, default=1.1)
    parser.add_argument("--model-version", type=str, default=None)
    parser.add_argument("--data-snapshot-id", type=str, default=None)
    parser.add_argument("--ruleset-path", type=str, default=None)
    parser.add_argument("--log-dir", type=str, default="game_logs")
    parser.add_argument("--manual", action="store_true", help="Step through plays manually.")
    parser.add_argument(
        "--seeded-rosters-only",
        action="store_true",
        help="Skip MLB API roster loading and use deterministic seeded rosters only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()

    seed = args.seed if args.seed is not None else settings.default_seed
    model_version = args.model_version or settings.default_model_version
    data_snapshot_id = args.data_snapshot_id or settings.default_data_snapshot_id
    ruleset_path = args.ruleset_path or settings.simulator_ruleset_path

    loaded_ruleset = load_ruleset_from_path(ruleset_path)
    scheduled_innings = (
        args.innings if args.innings is not None else loaded_ruleset.ruleset.scheduled_innings
    )

    loaded_rosters = asyncio.run(
        load_watch_rosters(
            home_team_id=args.home_team_id,
            away_team_id=args.away_team_id,
            seed=seed,
            home_team_name_override=args.home_team_name,
            away_team_name_override=args.away_team_name,
            use_api_rosters=not args.seeded_rosters_only,
            settings=settings,
        )
    )
    home_roster = loaded_rosters.home.roster
    away_roster = loaded_rosters.away.roster

    print(
        f"[roster] home={loaded_rosters.home.source} away={loaded_rosters.away.source}",
        file=sys.stderr,
    )
    if loaded_rosters.home.note is not None:
        print(
            f"[roster] home_team_id={home_roster.team_id}: {loaded_rosters.home.note}",
            file=sys.stderr,
        )
    if loaded_rosters.away.note is not None:
        print(
            f"[roster] away_team_id={away_roster.team_id}: {loaded_rosters.away.note}",
            file=sys.stderr,
        )

    trace = simulate_game_trace(
        seed=seed,
        home_team_id=args.home_team_id,
        away_team_id=args.away_team_id,
        scheduled_innings=scheduled_innings,
        ruleset=loaded_ruleset.ruleset,
        ruleset_checksum=loaded_ruleset.checksum_sha256,
    )

    match_id = create_match_id(
        seed=seed,
        model_version=model_version,
        data_snapshot_id=data_snapshot_id,
        home_team_id=args.home_team_id,
        away_team_id=args.away_team_id,
        scheduled_innings=scheduled_innings,
        ruleset_id=loaded_ruleset.ruleset.ruleset_id,
        ruleset_checksum=loaded_ruleset.checksum_sha256,
    )

    context = MatchContext(
        match_id=match_id,
        seed=seed,
        model_version=model_version,
        data_snapshot_id=data_snapshot_id,
        home_team_id=args.home_team_id,
        away_team_id=args.away_team_id,
        ruleset_id=loaded_ruleset.ruleset.ruleset_id,
        ruleset_checksum=loaded_ruleset.checksum_sha256,
        scheduled_innings=scheduled_innings,
    )
    writer = GameLogWriter(log_dir=args.log_dir, context=context)
    writer.write_header(
        extra={
            "home_team_name": home_roster.team_name,
            "away_team_name": away_roster.team_name,
            "ruleset_path": loaded_ruleset.source_path,
            "home_roster_source": loaded_rosters.home.source,
            "away_roster_source": loaded_rosters.away.source,
            "home_roster_note": loaded_rosters.home.note,
            "away_roster_note": loaded_rosters.away.note,
        }
    )

    playback = PlaybackController(
        delay_seconds=max(0.0, args.delay_seconds),
        paused=args.manual,
    )
    rendered = run_watch_loop(
        trace=trace,
        playback=playback,
        writer=writer,
        match_id=match_id,
        home_roster=home_roster,
        away_roster=away_roster,
        ruleset_id=loaded_ruleset.ruleset.ruleset_id,
    )

    writer.write_summary(
        payload={
            "home_team_name": home_roster.team_name,
            "away_team_name": away_roster.team_name,
            "home_score": trace.result.home_score,
            "away_score": trace.result.away_score,
            "innings_played": trace.result.innings_played,
            "winner_team_id": trace.result.winner_team_id,
            "plays_total": len(trace.plays),
            "plays_rendered": rendered,
            "aborted": rendered < len(trace.plays),
            "assumptions": trace.result.assumptions,
            "line_score_home": trace.line_score_home,
            "line_score_away": trace.line_score_away,
            "home_roster_source": loaded_rosters.home.source,
            "away_roster_source": loaded_rosters.away.source,
            "home_roster_note": loaded_rosters.home.note,
            "away_roster_note": loaded_rosters.away.note,
        }
    )

    print(
        json.dumps(
            {
                "match_id": match_id,
                "jsonl_path": writer.jsonl_path.as_posix(),
                "summary_path": writer.summary_path.as_posix(),
                "plays_rendered": rendered,
                "plays_total": len(trace.plays),
            },
            indent=2,
            sort_keys=True,
        )
    )


class PlaybackController:
    def __init__(self, *, delay_seconds: float, paused: bool) -> None:
        self.delay_seconds = delay_seconds
        self.paused = paused
        self.quit_requested = False

    def wait_or_step(self) -> bool:
        if self.quit_requested:
            return False

        if self.paused:
            command = input("[paused] Enter=next  r=resume  q=quit > ").strip().lower()
            if command == "q":
                self.quit_requested = True
                return False
            if command == "r":
                self.paused = False
                return True
            return True

        nb_command = _read_nonblocking_command()
        if nb_command == "p":
            self.paused = True
            return True
        if nb_command == "q":
            self.quit_requested = True
            return False

        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        return True


def run_watch_loop(
    *,
    trace: GameSimulationTrace,
    playback: PlaybackController,
    writer: GameLogWriter,
    match_id: str,
    home_roster: SeededTeamRoster,
    away_roster: SeededTeamRoster,
    ruleset_id: str,
) -> int:
    recent_descriptions: list[str] = []
    rendered = 0
    total = len(trace.plays)

    for play in trace.plays:
        if not playback.wait_or_step():
            break

        rendered += 1
        writer.write_play(play=play)
        recent_descriptions.append(_play_line(play))
        if len(recent_descriptions) > 10:
            recent_descriptions.pop(0)

        frame = _render_frame(
            match_id=match_id,
            ruleset_id=ruleset_id,
            trace=trace,
            current_play=play,
            play_number=rendered,
            play_total=total,
            home_roster=home_roster,
            away_roster=away_roster,
            recent_descriptions=recent_descriptions,
            paused=playback.paused,
        )
        _draw_frame(frame)

    return rendered


def _render_frame(
    *,
    match_id: str,
    ruleset_id: str,
    trace: GameSimulationTrace,
    current_play: PlayTrace,
    play_number: int,
    play_total: int,
    home_roster: SeededTeamRoster,
    away_roster: SeededTeamRoster,
    recent_descriptions: list[str],
    paused: bool,
) -> str:
    batting_roster = (
        home_roster if current_play.batting_team_id == home_roster.team_id else away_roster
    )
    fielding_roster = (
        home_roster if current_play.fielding_team_id == home_roster.team_id else away_roster
    )

    bases = _bases_text(current_play.bases_after)
    status = "PAUSED" if paused else "LIVE"
    lines: list[str] = []
    lines.append(f"Match {match_id}  |  Ruleset {ruleset_id}  |  {status}")
    lines.append(
        f"Play {play_number}/{play_total}  |  "
        f"Inning {current_play.inning} {current_play.half.upper()}  |  "
        f"Outs {current_play.outs_after}"
    )
    lines.append(
        f"Score: {away_roster.team_name} {current_play.away_score_after_play} - "
        f"{home_roster.team_name} {current_play.home_score_after_play}"
    )
    lines.append("")
    lines.append(
        _line_score_text(
            trace=trace, home_name=home_roster.team_name, away_name=away_roster.team_name
        )
    )
    lines.append("")
    lines.append(f"Bases: {bases}")
    lines.append("")
    lines.append(_field_panel(roster=fielding_roster))
    lines.append("")
    lines.append(_lineup_panel(title=f"{away_roster.team_name} Lineup", roster=away_roster))
    lines.append("")
    lines.append(_lineup_panel(title=f"{home_roster.team_name} Lineup", roster=home_roster))
    lines.append("")
    lines.append(f"At Bat: {batting_roster.team_name}  |  Last Event: {current_play.event}")
    lines.append("Recent Plays:")
    for description in recent_descriptions:
        lines.append(f"- {description}")
    lines.append("")
    lines.append("Controls: type `p` + Enter to pause, `q` + Enter to quit while live.")
    lines.append("Paused controls: Enter=next, r=resume, q=quit.")
    return "\n".join(lines)


def _field_panel(*, roster: SeededTeamRoster) -> str:
    fielders = roster.fielders
    return "\n".join(
        [
            f"Defensive Field ({roster.team_name}):",
            f"               CF {fielders['CF'].full_name}",
            f"      LF {fielders['LF'].full_name}      RF {fielders['RF'].full_name}",
            f"               SS {fielders['SS'].full_name}",
            f"      3B {fielders['3B'].full_name}      2B {fielders['2B'].full_name}",
            f"               1B {fielders['1B'].full_name}",
            f"                C {fielders['C'].full_name}",
            f"                P {fielders['P'].full_name}",
        ]
    )


def _lineup_panel(*, title: str, roster: SeededTeamRoster) -> str:
    lines = [title]
    for index, player in enumerate(roster.lineup, start=1):
        lines.append(f"{index:>2}. {player.full_name:<18} {player.position}")
    return "\n".join(lines)


def _line_score_text(*, trace: GameSimulationTrace, home_name: str, away_name: str) -> str:
    innings = max(len(trace.line_score_home), len(trace.line_score_away))
    inning_header = " ".join(str(i) for i in range(1, innings + 1))
    away_row = " ".join(str(value) for value in trace.line_score_away)
    home_row = " ".join(str(value) for value in trace.line_score_home)
    return "\n".join(
        [
            f"Line Score:     {inning_header}",
            f"{away_name[:12]:<12} {away_row}",
            f"{home_name[:12]:<12} {home_row}",
        ]
    )


def _play_line(play: PlayTrace) -> str:
    return (
        f"#{play.play_index} {play.half[0].upper()}{play.inning} {play.event} | "
        f"{play.description} "
        f"({play.away_score_after_play}-{play.home_score_after_play})"
    )


def _bases_text(bases_key: str) -> str:
    first = "1B" if bases_key[0] == "1" else "--"
    second = "2B" if bases_key[1] == "1" else "--"
    third = "3B" if bases_key[2] == "1" else "--"
    return f"{first} {second} {third}"


def _draw_frame(frame: str) -> None:
    if sys.stdout.isatty():
        print("\033[2J\033[H", end="")
    print(frame)


def _read_nonblocking_command() -> str | None:
    if not sys.stdin.isatty():
        return None
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return None
    value = sys.stdin.readline().strip().lower()
    return value if value != "" else None


if __name__ == "__main__":
    main()
