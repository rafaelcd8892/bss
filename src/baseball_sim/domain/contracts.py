from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


def utc_now() -> datetime:
    return datetime.now(UTC)


class DeterministicContext(BaseModel):
    """Deterministic execution contract for all stochastic endpoints."""

    model_config = ConfigDict(frozen=True)

    seed: int = Field(..., ge=0, le=4_294_967_295)
    model_version: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    data_snapshot_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )


class ResponseMeta(BaseModel):
    generated_at_utc: datetime = Field(default_factory=utc_now)
    context: DeterministicContext


class TeamSummary(BaseModel):
    team_id: PositiveInt
    name: str
    abbreviation: str | None = None
    league_name: str | None = None
    division_name: str | None = None


class TeamListResponse(BaseModel):
    teams: list[TeamSummary]


class PlayerSummary(BaseModel):
    player_id: PositiveInt
    full_name: str
    primary_position: str | None = None
    bats: str | None = None
    throws: str | None = None


class TeamRosterResponse(BaseModel):
    team_id: PositiveInt
    players: list[PlayerSummary]


#: Whether a reported value was computed from ingested data or is a seeded
#: placeholder. Exposed per metric so a client can visibly distinguish the two.
MetricSource = Literal["real", "synthetic"]


class TeamProfileFactors(BaseModel):
    """The seven [0, 1] matchup factors the simulator consumes."""

    offense: float = Field(..., ge=0.0, le=1.0)
    discipline: float = Field(..., ge=0.0, le=1.0)
    power: float = Field(..., ge=0.0, le=1.0)
    speed: float = Field(..., ge=0.0, le=1.0)
    prevention: float = Field(..., ge=0.0, le=1.0)
    command: float = Field(..., ge=0.0, le=1.0)
    range_factor: float = Field(..., ge=0.0, le=1.0)


class TeamProfileResponse(BaseModel):
    team_id: PositiveInt
    season: int
    #: "real" when built from ingested stats, "synthetic" when seed-derived.
    source: MetricSource
    factors: TeamProfileFactors
    #: Aggregate inputs behind the factors, so the numbers can be audited.
    team_woba: float | None = None
    team_fip: float | None = None
    batters_counted: int = Field(..., ge=0)
    pitchers_counted: int = Field(..., ge=0)


class PlayerSeasonLine(BaseModel):
    """One player's season line for a stat group, with the metrics computed from it."""

    stat_group: Literal["hitting", "pitching"]
    team_id: int | None = None
    plate_appearances: int | None = None
    at_bats: int | None = None
    hits: int | None = None
    doubles: int | None = None
    triples: int | None = None
    home_runs: int | None = None
    walks: int | None = None
    strikeouts: int | None = None
    stolen_bases: int | None = None
    innings_pitched: float | None = None
    woba: float | None = None
    wrc_plus: float | None = None
    fip: float | None = None
    k_bb_ratio: float | None = None


class PlayerSeasonResponse(BaseModel):
    player: PlayerSummary
    season: int
    lines: list[PlayerSeasonLine]


class TeamProfileListResponse(BaseModel):
    season: int
    teams: list[TeamProfileResponse]


LeaderMetric = Literal["woba", "wrc_plus", "fip", "k_bb_ratio"]


class StatLeader(BaseModel):
    rank: int = Field(..., ge=1)
    player_id: PositiveInt
    full_name: str
    team_id: int | None = None
    value: float
    plate_appearances: int | None = None
    innings_pitched: float | None = None


class StatLeadersResponse(BaseModel):
    metric: LeaderMetric
    season: int
    direction: Literal["higher_is_better", "lower_is_better"]
    #: Human-readable playing-time qualifier applied, e.g. "min 200 PA".
    qualifier: str
    leaders: list[StatLeader]


class ComparePlayersRequest(BaseModel):
    left_player_id: PositiveInt
    right_player_id: PositiveInt
    context: DeterministicContext


class MetricComparison(BaseModel):
    left_value: float
    right_value: float
    left_source: MetricSource
    right_source: MetricSource
    delta_left_minus_right: float
    better_player_id: PositiveInt
    direction: Literal["higher_is_better", "lower_is_better"]


class ComparePlayersResult(BaseModel):
    left_player_id: PositiveInt
    right_player_id: PositiveInt
    metrics: dict[str, MetricComparison]
    summary: str


class ComparePlayersResponse(BaseModel):
    meta: ResponseMeta
    result: ComparePlayersResult


class SimulateGameRequest(BaseModel):
    home_team_id: PositiveInt
    away_team_id: PositiveInt
    innings: int = Field(default=9, ge=9, le=20)
    context: DeterministicContext


class SimulateGameResult(BaseModel):
    home_team_id: PositiveInt
    away_team_id: PositiveInt
    innings_played: int = Field(..., ge=9, le=21)
    home_score: int = Field(..., ge=0)
    away_score: int = Field(..., ge=0)
    winner_team_id: PositiveInt
    assumptions: list[str]


class SimulateGameResponse(BaseModel):
    meta: ResponseMeta
    result: SimulateGameResult


PlayByPlayEventType = Literal[
    "out",
    "walk",
    "single",
    "double",
    "triple",
    "home_run",
    "tiebreaker",
]


class PlayByPlayEvent(BaseModel):
    play_index: int = Field(..., ge=1)
    inning: int = Field(..., ge=1)
    half: Literal["top", "bottom"]
    batting_team_id: PositiveInt
    fielding_team_id: PositiveInt
    event: PlayByPlayEventType
    outs_before: int = Field(..., ge=0, le=3)
    outs_after: int = Field(..., ge=0, le=3)
    bases_before: str = Field(..., pattern=r"^[01]{3}$")
    bases_after: str = Field(..., pattern=r"^[01]{3}$")
    runs_scored_on_play: int = Field(..., ge=0)
    home_score_after_play: int = Field(..., ge=0)
    away_score_after_play: int = Field(..., ge=0)
    description: str
    batter_id: int | None = None
    batter_name: str | None = None
    #: Home win probability after this play, from the shared baseline model. Carried
    #: with the play so a client never has to reimplement the model to draw it.
    home_win_probability: float = Field(..., ge=0.0, le=1.0)


class SimulateGamePlayByPlayResult(BaseModel):
    #: Deterministic identity of this matchup: the same context always yields the same
    #: id, and the same game. Use it to build a replay link.
    match_id: str
    summary: SimulateGameResult
    line_score_home: list[int]
    line_score_away: list[int]
    plays: list[PlayByPlayEvent]


class SimulateGamePlayByPlayResponse(BaseModel):
    meta: ResponseMeta
    result: SimulateGamePlayByPlayResult


class SimulationRunResponse(BaseModel):
    """A stored run, enough to reproduce the game exactly.

    Deterministic simulation means the inputs are the replay: the stored summary is
    kept as an audit record so a later run can be checked against it, not because the
    game needs it to be reconstructed.
    """

    match_id: str
    created_at_utc: datetime
    home_team_id: PositiveInt
    away_team_id: PositiveInt
    innings: int
    context: DeterministicContext
    #: Which stats source served the run, for lineage.
    stats_source: str
    summary: SimulateGameResult


class PredictGameRequest(BaseModel):
    home_team_id: PositiveInt
    away_team_id: PositiveInt
    context: DeterministicContext


class PredictGameResult(BaseModel):
    home_team_id: PositiveInt
    away_team_id: PositiveInt
    home_win_probability: float = Field(..., ge=0.0, le=1.0)
    away_win_probability: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    #: "real" only when both clubs' profiles came from ingested stats.
    source: MetricSource
    #: The run rates the probability is built from, so it can be audited.
    home_expected_runs: float
    away_expected_runs: float
    explanation: list[str]


class PredictGameResponse(BaseModel):
    meta: ResponseMeta
    result: PredictGameResult
