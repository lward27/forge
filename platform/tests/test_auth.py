from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from forge_platform.app import app
from forge_platform.database import get_session
from forge_platform.middleware.auth import get_api_key
from forge_platform.services.auth_service import generate_key, hash_key, key_prefix

import tests.conftest  # noqa: F401

client = TestClient(app)

TENANT_ID = "00000000-0000-0000-0000-000000000001"


# ── Key generation unit tests ──────────────────────────────────────────


def test_generate_key_format():
    key = generate_key()
    assert key.startswith("forge_")
    assert len(key) > 20


def test_hash_key_deterministic():
    key = "forge_test123"
    assert hash_key(key) == hash_key(key)


def test_hash_key_different_inputs():
    assert hash_key("forge_a") != hash_key("forge_b")


def test_key_prefix_length():
    key = "forge_abcdefgh"
    assert key_prefix(key) == "forge_ab"


# ── Auth endpoint tests ──────────────────────────────────────────


@patch("forge_platform.services.auth_service.create_api_key")
def test_create_admin_key(mock_create):
    mock_key = MagicMock()
    mock_key.id = "00000000-0000-0000-0000-000000000099"
    mock_key.key_prefix = "forge_ab"
    mock_key.name = "Test Admin"
    mock_key.role = "admin"
    mock_key.tenant_id = None
    mock_key.created_at = "2026-03-25T12:00:00"
    mock_create.return_value = (mock_key, "forge_abcdef123")

    response = client.post(
        "/auth/keys",
        json={"name": "Test Admin", "role": "admin"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["key"] == "forge_abcdef123"
    assert data["role"] == "admin"


@patch("forge_platform.services.auth_service.create_api_key")
def test_create_tenant_key(mock_create):
    mock_key = MagicMock()
    mock_key.id = "00000000-0000-0000-0000-000000000099"
    mock_key.key_prefix = "forge_cd"
    mock_key.name = "Tenant Key"
    mock_key.role = "tenant"
    mock_key.tenant_id = TENANT_ID
    mock_key.created_at = "2026-03-25T12:00:00"
    mock_create.return_value = (mock_key, "forge_cdefgh456")

    response = client.post(
        "/auth/keys",
        json={"name": "Tenant Key", "role": "tenant", "tenant_id": TENANT_ID},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "tenant"
    assert response.json()["tenant_id"] == TENANT_ID


def test_create_tenant_key_missing_tenant_id():
    response = client.post(
        "/auth/keys",
        json={"name": "Bad Key", "role": "tenant"},
    )
    assert response.status_code == 400
    assert "tenant_id required" in response.json()["detail"]


def test_create_admin_key_with_tenant_id():
    response = client.post(
        "/auth/keys",
        json={"name": "Bad Key", "role": "admin", "tenant_id": TENANT_ID},
    )
    assert response.status_code == 400
    assert "must not be set" in response.json()["detail"]


def test_create_key_invalid_role():
    response = client.post(
        "/auth/keys",
        json={"name": "Bad Key", "role": "superuser"},
    )
    assert response.status_code == 422


@patch("forge_platform.services.auth_service.list_keys", return_value=[])
def test_list_keys_empty(mock_list):
    response = client.get("/auth/keys")
    assert response.status_code == 200
    assert response.json() == {"keys": []}


@patch("forge_platform.services.auth_service.revoke_key")
def test_revoke_key(mock_revoke):
    mock_key = MagicMock()
    mock_key.id = "00000000-0000-0000-0000-000000000099"
    mock_key.is_active = False
    mock_revoke.return_value = mock_key

    response = client.delete("/auth/keys/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@patch("forge_platform.services.auth_service.revoke_key", return_value=None)
def test_revoke_key_not_found(mock_revoke):
    response = client.delete("/auth/keys/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404


# ── Middleware tests (override get_api_key per-test) ──────────────────


def test_no_api_key_returns_401():
    # Temporarily remove the mock auth override
    original = app.dependency_overrides.get(get_api_key)
    app.dependency_overrides.pop(get_api_key, None)

    # Also need a real session mock since middleware calls validate_key
    from unittest.mock import MagicMock
    from sqlmodel import Session

    def _mock_sess():
        yield MagicMock(spec=Session)

    app.dependency_overrides[get_session] = _mock_sess

    try:
        no_auth_client = TestClient(app)
        response = no_auth_client.get("/tenants")
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]
    finally:
        # Restore
        if original:
            app.dependency_overrides[get_api_key] = original
        import tests.conftest  # re-apply
        app.dependency_overrides[get_api_key] = tests.conftest._mock_admin_key


def test_health_no_auth_required():
    # Health should work even without auth override
    original = app.dependency_overrides.get(get_api_key)
    app.dependency_overrides.pop(get_api_key, None)

    try:
        no_auth_client = TestClient(app)
        response = no_auth_client.get("/health")
        assert response.status_code == 200
    finally:
        if original:
            app.dependency_overrides[get_api_key] = original
        import tests.conftest
        app.dependency_overrides[get_api_key] = tests.conftest._mock_admin_key
