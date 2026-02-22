from typing import Annotated

from fastapi import APIRouter, Depends

from baseball_sim.config import Settings, get_settings
from baseball_sim.domain.contracts import (
    ComparePlayersRequest,
    ComparePlayersResponse,
    PredictGameRequest,
    PredictGameResponse,
    ResponseMeta,
    SimulateGameRequest,
    SimulateGameResponse,
)
from baseball_sim.domain.service import compare_players, predict_game, simulate_game
from baseball_sim.sim.rulesets import load_ruleset_from_path

router = APIRouter()
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/health")
def health(settings: SettingsDependency) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@router.post("/compare/players", response_model=ComparePlayersResponse)
def compare_players_endpoint(request: ComparePlayersRequest) -> ComparePlayersResponse:
    result = compare_players(request)
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
    )
    return SimulateGameResponse(meta=ResponseMeta(context=request.context), result=result)


@router.post("/predict/game", response_model=PredictGameResponse)
def predict_game_endpoint(request: PredictGameRequest) -> PredictGameResponse:
    result = predict_game(request)
    return PredictGameResponse(meta=ResponseMeta(context=request.context), result=result)
