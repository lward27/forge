from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlmodel import Session

from forge_platform.app import app
from forge_platform.database import get_session


def get_mock_session():
    session = MagicMock(spec=Session)
    yield session


app.dependency_overrides[get_session] = get_mock_session

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}
