from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from baseball_sim.config import Settings, get_settings
from baseball_sim.domain.career import batting_total, pitching_total
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
    PlayerCareerResponse,
    PlayerSeasonLine,
    PlayerSeasonResponse,
    PlayerSummary,
    PredictGameRequest,
    PredictGameResponse,
    ResponseMeta,
    SeasonLines,
    SimulateGamePlayByPlayResponse,
    SimulateGameRequest,
    SimulateGameResponse,
    SimulationRunResponse,
    StatLeadersResponse,
    TeamListResponse,
    TeamProfileFactors,
    TeamProfileListResponse,
    TeamProfileResponse,
    TeamRosterResponse,
)
from baseball_sim.domain.provider_factory import get_lineup_provider, get_stats_provider
from baseball_sim.domain.service import (
    compare_players,
    predict_game,
    simulate_game,
    simulate_game_play_by_play,
)
from baseball_sim.domain.simulation_runs import (
    PostgresSimulationRunRepository,
    SimulationRunRepository,
)
from baseball_sim.sim.profiles import (
    aggregate_batting,
    aggregate_pitching,
    league_range_factors,
    synthetic_team_profile,
    team_profile_from_stats,
)
from baseball_sim.sim.rulesets import load_ruleset_from_path
from baseball_sim.sim.sabermetrics import (
    RawBattingLine,
    RawFieldingLine,
    RawPitchingLine,
    compute_fip,
    compute_woba,
)

router = APIRouter()
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_catalog_repository(settings: SettingsDependency) -> Iterator[CatalogRepository]:
    repository = PostgresCatalogRepository(dsn=settings.db_dsn)
    try:
        yield repository
    finally:
        repository.close()


CatalogDependency = Annotated[CatalogRepository, Depends(get_catalog_repository)]


def get_simulation_run_repository(
    settings: SettingsDependency,
) -> Iterator[SimulationRunRepository]:
    repository = PostgresSimulationRunRepository(dsn=settings.db_dsn)
    try:
        yield repository
    finally:
        repository.close()


def get_optional_run_recorder(
    settings: SettingsDependency,
) -> Iterator[SimulationRunRepository | None]:
    """A recorder only when recording is switched on.

    Opening a connection unconditionally would make the game viewer require a database
    it does not otherwise need, so this yields None when persistence is off.
    """

    if not settings.persist_simulation_runs:
        yield None
        return
    repository = PostgresSimulationRunRepository(dsn=settings.db_dsn)
    try:
        yield repository
    finally:
        repository.close()


RunDependency = Annotated[SimulationRunRepository, Depends(get_simulation_run_repository)]
RecorderDependency = Annotated[
    SimulationRunRepository | None, Depends(get_optional_run_recorder)
]


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


def _league_baselines(
    fielding_by_team: dict[int, list[RawFieldingLine]],
) -> dict[str, float] | None:
    """League range factor per position, or ``None`` when nothing was ingested."""

    lines = [line for club in fielding_by_team.values() for line in club]
    return league_range_factors(lines) or None if lines else None


def _team_profile_response(
    *,
    team_id: int,
    season: int,
    batting: list[RawBattingLine],
    pitching: list[RawPitchingLine],
    fielding: list[RawFieldingLine],
    league_range_baselines: dict[str, float] | None,
    fallback_seed: int,
) -> TeamProfileResponse:
    """Build one club's profile, labelling whether it came from data or the seed."""

    profile = team_profile_from_stats(
        batting_lines=batting,
        pitching_lines=pitching,
        fielding_lines=fielding,
        league_range_baselines=league_range_baselines,
    )
    if profile is None:
        # No ingested stats for this team: report the seed-derived fallback the
        # simulator would actually use, clearly labelled as synthetic.
        return TeamProfileResponse(
            team_id=team_id,
            season=season,
            source="synthetic",
            factors=TeamProfileFactors(
                **vars(synthetic_team_profile(seed=fallback_seed, team_id=team_id))
            ),
            batters_counted=0,
            pitchers_counted=0,
        )

    return TeamProfileResponse(
        team_id=team_id,
        season=season,
        source="real",
        factors=TeamProfileFactors(**vars(profile)),
        team_woba=round(compute_woba(aggregate_batting(batting)), 4) if batting else None,
        team_fip=round(compute_fip(aggregate_pitching(pitching)), 3) if pitching else None,
        batters_counted=len(batting),
        pitchers_counted=len(pitching),
        fielders_counted=len(fielding) if league_range_baselines else 0,
    )


@router.get("/teams/{team_id}/profile", response_model=TeamProfileResponse)
def get_team_profile_endpoint(
    team_id: int,
    catalog: CatalogDependency,
    settings: SettingsDependency,
    season: int | None = None,
) -> TeamProfileResponse:
    resolved_season = season if season is not None else settings.stats_season
    batting, pitching = catalog.get_team_stat_lines(team_id=team_id, season=resolved_season)
    fielding_by_team = catalog.get_league_fielding_lines(season=resolved_season)
    return _team_profile_response(
        team_id=team_id,
        season=resolved_season,
        batting=batting,
        pitching=pitching,
        fielding=fielding_by_team.get(team_id, []),
        league_range_baselines=_league_baselines(fielding_by_team),
        fallback_seed=settings.default_seed,
    )


@router.get("/stats/teams", response_model=TeamProfileListResponse)
def team_profiles_endpoint(
    catalog: CatalogDependency,
    settings: SettingsDependency,
    season: int | None = None,
) -> TeamProfileListResponse:
    resolved_season = season if season is not None else settings.stats_season
    by_team = catalog.get_all_team_stat_lines(season=resolved_season)
    fielding_by_team = catalog.get_league_fielding_lines(season=resolved_season)
    baselines = _league_baselines(fielding_by_team)
    teams = [
        _team_profile_response(
            team_id=team_id,
            season=resolved_season,
            batting=batting,
            pitching=pitching,
            fielding=fielding_by_team.get(team_id, []),
            league_range_baselines=baselines,
            fallback_seed=settings.default_seed,
        )
        for team_id, (batting, pitching) in sorted(by_team.items())
    ]
    return TeamProfileListResponse(season=resolved_season, teams=teams)


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


@router.get("/players/{player_id}/season", response_model=PlayerSeasonResponse)
def get_player_season_endpoint(
    player_id: int,
    catalog: CatalogDependency,
    settings: SettingsDependency,
    season: int | None = None,
) -> PlayerSeasonResponse:
    player = catalog.get_player(player_id=player_id)
    if player is None:
        raise HTTPException(status_code=404, detail=f"player {player_id} not found")

    available = catalog.get_player_seasons(player_id=player_id)
    # Default to the configured season, but fall back to the newest the player actually
    # has: a career backfill often ends before the current year for a retired player.
    resolved_season = season if season is not None else settings.stats_season
    if season is None and available and resolved_season not in available:
        resolved_season = available[0]
    return PlayerSeasonResponse(
        player=player,
        season=resolved_season,
        lines=catalog.get_player_season_lines(player_id=player_id, season=resolved_season),
        available_seasons=available,
    )


@router.get("/players/{player_id}/career", response_model=PlayerCareerResponse)
def get_player_career_endpoint(
    player_id: int, catalog: CatalogDependency
) -> PlayerCareerResponse:
    """Every ingested season for one player, newest first.

    Only as deep as the backfill has run: without `--history` this is the single
    season that was ingested, which is a shorter answer rather than a wrong one.
    """

    player = catalog.get_player(player_id=player_id)
    if player is None:
        raise HTTPException(status_code=404, detail=f"player {player_id} not found")

    by_season: dict[int, list[PlayerSeasonLine]] = {}
    for season, line in catalog.get_player_career(player_id=player_id):
        by_season.setdefault(season, []).append(line)

    batting, pitching = catalog.get_player_career_raw(player_id=player_id)
    totals = [
        total
        for total in (batting_total(batting), pitching_total(pitching))
        if total is not None
    ]
    return PlayerCareerResponse(
        player=player,
        seasons=[
            SeasonLines(season=season, lines=lines)
            for season, lines in sorted(by_season.items(), reverse=True)
        ],
        totals=totals,
    )


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
    recorder: RecorderDependency,
) -> SimulateGamePlayByPlayResponse:
    loaded_ruleset = load_ruleset_from_path(settings.simulator_ruleset_path)
    result = simulate_game_play_by_play(
        request,
        ruleset=loaded_ruleset.ruleset,
        ruleset_checksum=loaded_ruleset.checksum_sha256,
        provider=get_stats_provider(settings),
        lineup_provider=get_lineup_provider(settings),
    )

    if recorder is not None:
        # Opt-in, and deliberately not swallowed: if recording was asked for and it
        # fails, that is a real failure the caller should hear about.
        recorder.record_run(
            match_id=result.match_id,
            context=request.context,
            home_team_id=request.home_team_id,
            away_team_id=request.away_team_id,
            innings=request.innings,
            stats_source=settings.stats_source,
            summary=result.summary,
            ruleset=loaded_ruleset.ruleset,
            ruleset_checksum=loaded_ruleset.checksum_sha256,
        )

    return SimulateGamePlayByPlayResponse(
        meta=ResponseMeta(context=request.context), result=result
    )


@router.get(
    "/games/{match_id}/play-by-play", response_model=SimulateGamePlayByPlayResponse
)
def replay_simulation_run_endpoint(
    match_id: str,
    runs: RunDependency,
    settings: SettingsDependency,
) -> SimulateGamePlayByPlayResponse:
    """Replay a recorded game under the rules it was recorded under.

    Re-simulating with today's ruleset would quietly hand back a different game every
    time the model is retuned. A run with no stored ruleset predates that guarantee and
    is refused rather than replayed under rules it never saw.
    """

    run = runs.get_run(match_id=match_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no recorded run for {match_id}")
    ruleset = runs.get_run_ruleset(match_id=match_id)
    if ruleset is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"run {match_id} was recorded before its ruleset was stored, "
                "so it cannot be replayed faithfully"
            ),
        )

    result = simulate_game_play_by_play(
        SimulateGameRequest(
            home_team_id=run.home_team_id,
            away_team_id=run.away_team_id,
            innings=run.innings,
            context=run.context,
        ),
        ruleset=ruleset,
        ruleset_checksum=run.ruleset_checksum or "",
        provider=get_stats_provider(settings),
        lineup_provider=get_lineup_provider(settings),
    )
    return SimulateGamePlayByPlayResponse(
        meta=ResponseMeta(context=run.context), result=result
    )


@router.get("/games/{match_id}", response_model=SimulationRunResponse)
def get_simulation_run_endpoint(match_id: str, runs: RunDependency) -> SimulationRunResponse:
    run = runs.get_run(match_id=match_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no recorded run for {match_id}")
    return run


@router.post("/predict/game", response_model=PredictGameResponse)
def predict_game_endpoint(
    request: PredictGameRequest,
    settings: SettingsDependency,
) -> PredictGameResponse:
    result = predict_game(request, provider=get_stats_provider(settings))
    return PredictGameResponse(meta=ResponseMeta(context=request.context), result=result)
