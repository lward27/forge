from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from forge_platform.app import app
from forge_platform.database import get_session


def get_mock_session():
    session = MagicMock(spec=Session)
    yield session


app.dependency_overrides[get_session] = get_mock_session

client = TestClient(app)


@patch("forge_platform.services.tenant_service.get_tenant_by_name", return_value=None)
@patch("forge_platform.services.tenant_service.create_tenant")
def test_create_tenant(mock_create, mock_get_by_name):
    mock_tenant = MagicMock()
    mock_tenant.id = "00000000-0000-0000-0000-000000000001"
    mock_tenant.name = "test-app"
    mock_tenant.display_name = "Test App"
    mock_tenant.namespace = "forge-tenant-test-app"
    mock_tenant.status = "active"
    mock_tenant.resource_limits = {"cpu": "2", "memory": "4Gi", "storage": "20Gi"}
    mock_tenant.created_at = "2026-03-24T18:00:00"
    mock_create.return_value = mock_tenant

    response = client.post(
        "/tenants",
        json={"name": "test-app", "display_name": "Test App"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-app"
    assert data["namespace"] == "forge-tenant-test-app"
    assert data["status"] == "active"


@patch("forge_platform.services.tenant_service.get_tenant_by_name")
def test_create_tenant_duplicate(mock_get_by_name):
    mock_get_by_name.return_value = MagicMock()

    response = client.post(
        "/tenants",
        json={"name": "test-app", "display_name": "Test App"},
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_create_tenant_invalid_name():
    response = client.post(
        "/tenants",
        json={"name": "INVALID", "display_name": "Bad Name"},
    )
    assert response.status_code == 422


def test_create_tenant_name_too_short():
    response = client.post(
        "/tenants",
        json={"name": "a", "display_name": "Too Short"},
    )
    assert response.status_code == 422


@patch("forge_platform.services.tenant_service.list_tenants", return_value=[])
def test_list_tenants_empty(mock_list):
    response = client.get("/tenants")
    assert response.status_code == 200
    assert response.json() == {"tenants": []}


@patch("forge_platform.services.tenant_service.get_tenant", return_value=None)
def test_get_tenant_not_found(mock_get):
    response = client.get("/tenants/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404


@patch("forge_platform.services.tenant_service.delete_tenant", return_value=None)
def test_delete_tenant_not_found(mock_delete):
    response = client.delete("/tenants/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404


@patch("forge_platform.services.tenant_service.delete_tenant")
def test_delete_tenant(mock_delete):
    mock_tenant = MagicMock()
    mock_tenant.id = "00000000-0000-0000-0000-000000000001"
    mock_tenant.name = "test-app"
    mock_tenant.status = "deleted"
    mock_delete.return_value = mock_tenant

    response = client.delete("/tenants/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
