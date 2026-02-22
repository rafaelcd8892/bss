from fastapi.testclient import TestClient

from baseball_sim.main import app


def test_health_endpoint_returns_service_metadata() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "baseball-sim"
    assert payload["environment"] == "dev"
