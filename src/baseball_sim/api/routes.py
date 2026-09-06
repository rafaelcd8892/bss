from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from baseball_sim.config import Settings, get_settings
from baseball_sim.domain.catalog import (
    LEADER_METRICS,
    CatalogRepository,
    PostgresCatalogRepository,
    leader_qualifier_label,
)
from baseball_sim.domain.contracts import (
    ComparePlayersRequest,
    ComparePlayersResponse,
    LeaderMetric,
    PlayerSummary,
    PredictGameRequest,
    PredictGameResponse,
    ResponseMeta,
    SimulateGamePlayByPlayResponse,
    SimulateGameRequest,
    SimulateGameResponse,
    StatLeadersResponse,
    TeamListResponse,
    TeamRosterResponse,
)
from baseball_sim.domain.provider_factory import get_lineup_provider, get_stats_provider
from baseball_sim.domain.service import (
    compare_players,
    predict_game,
    simulate_game,
    simulate_game_play_by_play,
)
from baseball_sim.sim.rulesets import load_ruleset_from_path

router = APIRouter()
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_catalog_repository(settings: SettingsDependency) -> Iterator[CatalogRepository]:
    repository = PostgresCatalogRepository(dsn=settings.db_dsn)
    try:
        yield repository
    finally:
        repository.close()


CatalogDependency = Annotated[CatalogRepository, Depends(get_catalog_repository)]


@router.get("/health")
def health(settings: SettingsDependency) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@router.get("/teams", response_model=TeamListResponse)
def list_teams_endpoint(catalog: CatalogDependency) -> TeamListResponse:
    return TeamListResponse(teams=catalog.list_teams())


@router.get("/teams/{team_id}/roster", response_model=TeamRosterResponse)
def get_team_roster_endpoint(team_id: int, catalog: CatalogDependency) -> TeamRosterResponse:
    return TeamRosterResponse(team_id=team_id, players=catalog.get_team_roster(team_id=team_id))


@router.get("/stats/leaders", response_model=StatLeadersResponse)
def stat_leaders_endpoint(
    catalog: CatalogDependency,
    settings: SettingsDependency,
    metric: LeaderMetric = "woba",
    season: int | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    minimum: float | None = Query(
        default=None,
        ge=0,
        description="Playing-time qualifier (PA for hitting, IP for pitching).",
    ),
) -> StatLeadersResponse:
    meta = LEADER_METRICS[metric]
    resolved_season = season if season is not None else settings.stats_season
    resolved_minimum = minimum if minimum is not None else meta.default_minimum
    leaders = catalog.get_stat_leaders(
        metric=metric, season=resolved_season, minimum=resolved_minimum, limit=limit
    )
    return StatLeadersResponse(
        metric=metric,
        season=resolved_season,
        direction="higher_is_better" if meta.descending else "lower_is_better",
        qualifier=leader_qualifier_label(metric, resolved_minimum),
        leaders=leaders,
    )


@router.get("/players/{player_id}", response_model=PlayerSummary)
def get_player_endpoint(player_id: int, catalog: CatalogDependency) -> PlayerSummary:
    player = catalog.get_player(player_id=player_id)
    if player is None:
        raise HTTPException(status_code=404, detail=f"player {player_id} not found")
    return player


@router.post("/compare/players", response_model=ComparePlayersResponse)
def compare_players_endpoint(
    request: ComparePlayersRequest,
    settings: SettingsDependency,
) -> ComparePlayersResponse:
    result = compare_players(request, provider=get_stats_provider(settings))
    return ComparePlayersResponse(meta=ResponseMeta(context=request.context), result=result)


@router.post("/simulate/game", response_model=SimulateGameResponse)
def simulate_game_endpoint(
    request: SimulateGameRequest,
    settings: SettingsDependency,
) -> SimulateGameResponse:
    loaded_ruleset = load_ruleset_from_path(settings.simulator_ruleset_path)
    result = simulate_game(
        request,
        ruleset=loaded_ruleset.ruleset,
        ruleset_checksum=loaded_ruleset.checksum_sha256,
        provider=get_stats_provider(settings),
    )
    return SimulateGameResponse(meta=ResponseMeta(context=request.context), result=result)


@router.post("/simulate/game/play-by-play", response_model=SimulateGamePlayByPlayResponse)
def simulate_game_play_by_play_endpoint(
    request: SimulateGameRequest,
    settings: SettingsDependency,
) -> SimulateGamePlayByPlayResponse:
    loaded_ruleset = load_ruleset_from_path(settings.simulator_ruleset_path)
    result = simulate_game_play_by_play(
        request,
        ruleset=loaded_ruleset.ruleset,
        ruleset_checksum=loaded_ruleset.checksum_sha256,
        provider=get_stats_provider(settings),
        lineup_provider=get_lineup_provider(settings),
    )
    return SimulateGamePlayByPlayResponse(
        meta=ResponseMeta(context=request.context), result=result
    )


@router.post("/predict/game", response_model=PredictGameResponse)
def predict_game_endpoint(request: PredictGameRequest) -> PredictGameResponse:
    result = predict_game(request)
    return PredictGameResponse(meta=ResponseMeta(context=request.context), result=result)
