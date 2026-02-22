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


class ComparePlayersRequest(BaseModel):
    left_player_id: PositiveInt
    right_player_id: PositiveInt
    context: DeterministicContext


class MetricComparison(BaseModel):
    left_value: float
    right_value: float
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
    explanation: list[str]


class PredictGameResponse(BaseModel):
    meta: ResponseMeta
    result: PredictGameResult
