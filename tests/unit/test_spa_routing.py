"""The SPA mount must resolve client routes without swallowing API 404s."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from baseball_sim.main import app

FRONTEND_BUILD = Path("frontend/dist/index.html")
needs_build = pytest.mark.skipif(
    not FRONTEND_BUILD.exists(),
    reason="frontend build not present (CI installs Python only)",
)


def test_unknown_api_path_returns_json_404() -> None:
    """Runs with or without a build: a missing endpoint must never answer HTML."""
    response = TestClient(app).get("/api/v1/definitely-not-a-route")

    assert response.status_code == 404
    assert "application/json" in response.headers.get("content-type", "")


@needs_build
@pytest.mark.parametrize("path", ["/game", "/analyze", "/analyze/leaders", "/explore"])
def test_client_routes_serve_the_spa_shell(path: str) -> None:
    response = TestClient(app).get(path)

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert 'id="root"' in response.text


@needs_build
def test_api_routes_still_win_over_the_static_mount() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
