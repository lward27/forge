from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from forge_platform.app import app

import tests.conftest  # noqa: F401

client = TestClient(app)

TENANT_ID = "00000000-0000-0000-0000-000000000001"
DB_ID = "00000000-0000-0000-0000-000000000002"


def _mock_tenant():
    tenant = MagicMock()
    tenant.id = TENANT_ID
    tenant.name = "test-app"
    tenant.namespace = "forge-tenant-test-app"
    tenant.status = "active"
    return tenant


def _mock_db():
    db = MagicMock()
    db.id = DB_ID
    db.tenant_id = TENANT_ID
    db.name = "inventory"
    db.pg_database = "forge_t_test_app_inventory"
    db.pg_role = "forge_t_test_app_inventory_role"
    db.secret_name = "forge-db-inventory"
    db.status = "active"
    db.created_at = "2026-03-25T12:00:00"
    return db


@patch("forge_platform.routers.databases.tenant_service.get_tenant")
@patch("forge_platform.services.database_service.get_database_by_name", return_value=None)
@patch("forge_platform.services.database_service.create_database")
def test_create_database(mock_create, mock_get_by_name, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_create.return_value = _mock_db()

    response = client.post(
        f"/tenants/{TENANT_ID}/databases",
        json={"name": "inventory"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "inventory"
    assert data["pg_database"] == "forge_t_test_app_inventory"
    assert data["secret_name"] == "forge-db-inventory"


@patch("forge_platform.routers.databases.tenant_service.get_tenant", return_value=None)
def test_create_database_tenant_not_found(mock_get_tenant):
    response = client.post(
        f"/tenants/{TENANT_ID}/databases",
        json={"name": "inventory"},
    )
    assert response.status_code == 404
    assert "Tenant not found" in response.json()["detail"]


@patch("forge_platform.routers.databases.tenant_service.get_tenant")
@patch("forge_platform.services.database_service.get_database_by_name")
def test_create_database_duplicate(mock_get_by_name, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_by_name.return_value = _mock_db()

    response = client.post(
        f"/tenants/{TENANT_ID}/databases",
        json={"name": "inventory"},
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_create_database_invalid_name():
    response = client.post(
        f"/tenants/{TENANT_ID}/databases",
        json={"name": "INVALID"},
    )
    assert response.status_code == 422


@patch("forge_platform.routers.databases.tenant_service.get_tenant")
@patch("forge_platform.services.database_service.list_databases", return_value=[])
def test_list_databases_empty(mock_list, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()

    response = client.get(f"/tenants/{TENANT_ID}/databases")
    assert response.status_code == 200
    assert response.json() == {"databases": []}


@patch("forge_platform.routers.databases.tenant_service.get_tenant")
@patch("forge_platform.services.database_service.get_database", return_value=None)
def test_get_database_not_found(mock_get, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()

    response = client.get(f"/tenants/{TENANT_ID}/databases/{DB_ID}")
    assert response.status_code == 404


@patch("forge_platform.routers.databases.tenant_service.get_tenant")
@patch("forge_platform.services.database_service.delete_database")
def test_delete_database(mock_delete, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_db = _mock_db()
    mock_db.status = "deleted"
    mock_delete.return_value = mock_db

    response = client.delete(f"/tenants/{TENANT_ID}/databases/{DB_ID}")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"


@patch("forge_platform.routers.databases.tenant_service.get_tenant")
@patch("forge_platform.services.database_service.delete_database", return_value=None)
def test_delete_database_not_found(mock_delete, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()

    response = client.delete(f"/tenants/{TENANT_ID}/databases/{DB_ID}")
    assert response.status_code == 404
