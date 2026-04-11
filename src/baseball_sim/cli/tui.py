from __future__ import annotations

import argparse
import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Footer, Header, RichLog, Static

from baseball_sim.config import get_settings
from baseball_sim.seeders.roster import SeededPlayer, SeededTeamRoster
from baseball_sim.sim.match_id import create_match_id
from baseball_sim.sim.rulesets import load_ruleset_from_path
from baseball_sim.sim.state_machine import GameSimulationTrace, PlayTrace, simulate_game_trace

from .game_log import GameLogWriter, MatchContext
from .roster_loader import load_watch_rosters

# ---------------------------------------------------------------------------
# Rich markup helpers
# ---------------------------------------------------------------------------

_OCC = "[bold yellow]◆[/bold yellow]"
_EMP = "[dim]◇[/dim]"

_EVENT_COLOR: dict[str, str] = {
    "home_run": "bold red",
    "triple": "bold magenta",
    "double": "bold yellow",
    "single": "green",
    "walk": "cyan",
    "out": "dim",
    "tiebreaker": "bold blue",
}


def _bases_diamond(bases_key: str) -> str:
    """Return a 3-line Rich markup diamond showing base occupancy.

    bases_key[0]=1B, bases_key[1]=2B, bases_key[2]=3B
    """
    b1 = _OCC if bases_key[0] == "1" else _EMP
    b2 = _OCC if bases_key[1] == "1" else _EMP
    b3 = _OCC if bases_key[2] == "1" else _EMP
    return (
        f"         {b2}\n"
        f"    {b3}       {b1}\n"
        f"         [dim]⌂[/dim]"
    )


def _outs_pips(outs: int) -> str:
    filled = "[bold red]●[/bold red]"
    empty = "[dim]○[/dim]"
    return " ".join([filled] * outs + [empty] * (3 - outs))


def _line_score_markup(
    trace: GameSimulationTrace,
    home_name: str,
    away_name: str,
    current_inning: int,
) -> str:
    cols = max(9, current_inning)
    header = "          " + "  ".join(f"{i:>2}" for i in range(1, cols + 1))

    def row(name: str, scores: list[int]) -> str:
        cells = [
            f"{scores[i]:>2}" if i < len(scores) else " [dim].[/dim]"
            for i in range(cols)
        ]
        return f"[bold]{name[:8]:<8}[/bold]  " + "  ".join(cells)

    return "\n".join([
        header,
        row(away_name, trace.line_score_away),
        row(home_name, trace.line_score_home),
    ])


def _field_markup(roster: SeededTeamRoster) -> str:
    f = roster.fielders

    def slot(key: str) -> str:
        p: SeededPlayer | None = f.get(key)
        name = p.full_name[:13] if p else "---"
        return f"[cyan]{key:<2}[/cyan] {name}"

    return "\n".join([
        f"[bold]Fielding · {roster.team_name}[/bold]",
        f"              {slot('CF')}",
        f"   {slot('LF')}    {slot('RF')}",
        f"              {slot('SS')}",
        f"   {slot('3B')}    {slot('2B')}",
        f"              {slot('1B')}",
        f"               {slot('C')}",
        f"               {slot('P')}",
    ])


def _lineup_markup(roster: SeededTeamRoster, active_idx: int) -> str:
    n = len(roster.lineup)
    lines = [f"[bold]{roster.team_name} Lineup[/bold]"]
    for i, player in enumerate(roster.lineup, start=1):
        is_active = active_idx >= 0 and (i - 1) == active_idx % n
        marker = "[bold green]▶[/bold green]" if is_active else " "
        lines.append(
            f"{marker} {i:>2}. {player.full_name:<16} [dim]{player.position}[/dim]"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Textual app
# ---------------------------------------------------------------------------


class BaseballSimApp(App[None]):
    TITLE = "baseball-sim"
    BINDINGS = [
        Binding("p", "pause", "Pause", show=True),
        Binding("r", "resume", "Resume", show=True),
        Binding("space", "step", "Step", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]
    DEFAULT_CSS = """
    Screen {
        layout: vertical;
    }
    #main {
        height: 1fr;
        layout: horizontal;
    }
    #left-panel {
        width: 32;
        border: solid $primary;
        padding: 0 1;
    }
    #center-panel {
        width: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    #right-panel {
        width: 38;
        border: solid $primary;
        padding: 0 1;
    }
    #play-log {
        height: 14;
        border: solid $accent;
    }
    Static {
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        *,
        trace: GameSimulationTrace,
        home_roster: SeededTeamRoster,
        away_roster: SeededTeamRoster,
        writer: GameLogWriter,
        match_id: str,
        ruleset_id: str,
        delay_seconds: float,
        start_paused: bool,
    ) -> None:
        super().__init__()
        self._trace = trace
        self._home = home_roster
        self._away = away_roster
        self._writer = writer
        self._match_id = match_id
        self._ruleset_id = ruleset_id
        self._delay = max(0.1, delay_seconds)
        self._start_paused = start_paused
        self._play_index = 0
        self._paused = start_paused
        self._timer: Timer | None = None

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="left-panel"):
                yield Static(id="score")
                yield Static(id="inning-outs")
                yield Static(id="bases")
            with Vertical(id="center-panel"):
                yield Static(id="line-score")
                yield Static(id="field")
            with Vertical(id="right-panel"):
                yield Static(id="away-lineup")
                yield Static(id="home-lineup")
        yield RichLog(id="play-log", markup=True, highlight=False)
        yield Footer()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self._refresh_ui()
        self._timer = self.set_interval(self._delay, self._advance)
        if self._start_paused and self._timer is not None:
            self._timer.pause()

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def _advance(self) -> None:
        total = len(self._trace.plays)
        if self._play_index >= total:
            if self._timer is not None:
                self._timer.stop()
            self._refresh_ui()
            return
        play = self._trace.plays[self._play_index]
        self._writer.write_play(play=play)
        self._play_index += 1
        self._refresh_ui(play)

    # ------------------------------------------------------------------
    # UI refresh
    # ------------------------------------------------------------------

    def _refresh_ui(self, play: PlayTrace | None = None) -> None:
        idx = self._play_index
        total = len(self._trace.plays)

        if idx >= total:
            status = "FINAL"
        elif self._paused:
            status = "[bold yellow]PAUSED[/bold yellow]"
        else:
            status = "[bold green]LIVE[/bold green]"

        self.sub_title = f"Play {idx}/{total}  ·  {self._match_id[:24]}"

        away_score = play.away_score_after_play if play else 0
        home_score = play.home_score_after_play if play else 0
        inning = play.inning if play else 1
        half = play.half.upper() if play else "PRE"
        outs = play.outs_after if play else 0
        bases = play.bases_after if play else "000"

        # Score panel
        away_bold = "[bold yellow]" if away_score > home_score else "[bold]"
        home_bold = "[bold yellow]" if home_score > away_score else "[bold]"
        self.query_one("#score", Static).update(
            f"{status}\n\n"
            f"{away_bold}{self._away.team_name}[/]  {away_score}\n"
            f"{home_bold}{self._home.team_name}[/]  {home_score}"
        )

        # Inning + outs
        self.query_one("#inning-outs", Static).update(
            f"[bold]{inning}[/bold] {half}\n"
            f"Outs  {_outs_pips(outs)}"
        )

        # Bases diamond
        self.query_one("#bases", Static).update(_bases_diamond(bases))

        # Line score
        self.query_one("#line-score", Static).update(
            _line_score_markup(self._trace, self._home.team_name, self._away.team_name, inning)
        )

        # Field + lineups depend on who is batting/fielding
        if play is not None:
            fielding = self._home if play.fielding_team_id == self._home.team_id else self._away
            is_away_batting = play.batting_team_id == self._away.team_id
        else:
            fielding = self._home  # top of 1st: home fields
            is_away_batting = True

        batter_idx = (idx - 1) % len(self._away.lineup) if idx > 0 else 0

        self.query_one("#field", Static).update(_field_markup(fielding))
        self.query_one("#away-lineup", Static).update(
            _lineup_markup(self._away, batter_idx if is_away_batting else -1)
        )
        self.query_one("#home-lineup", Static).update(
            _lineup_markup(self._home, batter_idx if not is_away_batting else -1)
        )

        # Play log entry
        if play is not None:
            log = self.query_one("#play-log", RichLog)
            color = _EVENT_COLOR.get(play.event, "white")
            half_char = "T" if play.half == "top" else "B"
            log.write(
                f"[{color}]#{play.play_index:<4} "
                f"{half_char}{play.inning} "
                f"{play.event.upper():<10}[/{color}] "
                f"{play.description}  "
                f"[dim]({play.away_score_after_play}–{play.home_score_after_play})[/dim]"
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_pause(self) -> None:
        if not self._paused and self._play_index < len(self._trace.plays):
            self._paused = True
            if self._timer is not None:
                self._timer.pause()
            self._refresh_status()

    def action_resume(self) -> None:
        if self._paused:
            self._paused = False
            if self._timer is not None:
                self._timer.resume()
            self._refresh_status()

    def action_step(self) -> None:
        if self._paused:
            self._advance()

    def _refresh_status(self) -> None:
        idx = self._play_index
        total = len(self._trace.plays)
        if self._paused:
            status = "[bold yellow]PAUSED[/bold yellow]"
        else:
            status = "[bold green]LIVE[/bold green]"
        play = self._trace.plays[idx - 1] if idx > 0 else None
        away_score = play.away_score_after_play if play else 0
        home_score = play.home_score_after_play if play else 0
        away_bold = "[bold yellow]" if away_score > home_score else "[bold]"
        home_bold = "[bold yellow]" if home_score > away_score else "[bold]"
        self.query_one("#score", Static).update(
            f"{status}\n\n"
            f"{away_bold}{self._away.team_name}[/]  {away_score}\n"
            f"{home_bold}{self._home.team_name}[/]  {home_score}"
        )
        self.sub_title = f"Play {idx}/{total}  ·  {self._match_id[:24]}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch a deterministic baseball simulation in a Textual TUI."
    )
    parser.add_argument("--home-team-id", type=int, required=True)
    parser.add_argument("--away-team-id", type=int, required=True)
    parser.add_argument("--home-team-name", type=str, default=None)
    parser.add_argument("--away-team-name", type=str, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--innings", type=int, default=None)
    parser.add_argument("--delay-seconds", type=float, default=0.8)
    parser.add_argument("--model-version", type=str, default=None)
    parser.add_argument("--data-snapshot-id", type=str, default=None)
    parser.add_argument("--ruleset-path", type=str, default=None)
    parser.add_argument("--log-dir", type=str, default="game_logs")
    parser.add_argument("--manual", action="store_true", help="Start paused; step with Space.")
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

    app = BaseballSimApp(
        trace=trace,
        home_roster=home_roster,
        away_roster=away_roster,
        writer=writer,
        match_id=match_id,
        ruleset_id=loaded_ruleset.ruleset.ruleset_id,
        delay_seconds=args.delay_seconds,
        start_paused=args.manual,
    )
    app.run()

    writer.write_summary(
        payload={
            "home_team_name": home_roster.team_name,
            "away_team_name": away_roster.team_name,
            "home_score": trace.result.home_score,
            "away_score": trace.result.away_score,
            "innings_played": trace.result.innings_played,
            "winner_team_id": trace.result.winner_team_id,
            "plays_total": len(trace.plays),
            "home_roster_source": loaded_rosters.home.source,
            "away_roster_source": loaded_rosters.away.source,
        }
    )


if __name__ == "__main__":
    main()
