from fastapi.testclient import TestClient

from app.main import create_app


def test_health_contract() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "relay-api"}


def test_only_foundation_routes_exist() -> None:
    paths = create_app().openapi()["paths"]
    assert set(paths) == {"/health"}
