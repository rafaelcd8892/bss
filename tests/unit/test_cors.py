from fastapi.testclient import TestClient

from baseball_sim.config import Settings
from baseball_sim.main import app


def test_cors_origin_list_parsing() -> None:
    assert Settings(cors_allow_origins="*").cors_origin_list() == ["*"]
    assert Settings(cors_allow_origins="  ").cors_origin_list() == ["*"]
    assert Settings(
        cors_allow_origins="https://a.test, https://b.test"
    ).cors_origin_list() == ["https://a.test", "https://b.test"]


def test_cors_header_on_simple_request() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"


def test_cors_preflight_allows_post() -> None:
    client = TestClient(app)
    response = client.options(
        "/api/v1/simulate/game/play-by-play",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
