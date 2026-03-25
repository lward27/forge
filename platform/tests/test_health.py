from fastapi.testclient import TestClient

from forge_platform.app import app

import tests.conftest  # noqa: F401 — ensure overrides are applied

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}
