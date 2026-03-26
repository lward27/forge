from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from forge_platform.app import app

import tests.conftest  # noqa: F401

client = TestClient(app)

TENANT_ID = "00000000-0000-0000-0000-000000000001"
DB_ID = "00000000-0000-0000-0000-000000000002"
BASE_URL = f"/tenants/{TENANT_ID}/databases/{DB_ID}/tables"


def _mock_tenant():
    t = MagicMock()
    t.id = TENANT_ID
    t.name = "test-app"
    t.namespace = "forge-tenant-test-app"
    t.status = "active"
    return t


def _mock_db():
    db = MagicMock()
    db.id = DB_ID
    db.tenant_id = TENANT_ID
    db.name = "inventory"
    db.pg_database = "forge_t_test_app_inventory"
    db.pg_role = "forge_t_test_app_inventory_role"
    db.status = "active"
    return db


def _mock_table_def():
    td = MagicMock()
    td.name = "customers"
    td.database_id = DB_ID
    td.status = "active"
    td.created_at = "2026-03-25T12:00:00"
    return td


def _mock_columns():
    id_col = MagicMock()
    id_col.name = "id"
    id_col.column_type = "serial"
    id_col.nullable = False
    id_col.primary_key = True
    id_col.unique = False
    id_col.default_value = None
    id_col.reference_table = None

    name_col = MagicMock()
    name_col.name = "name"
    name_col.column_type = "text"
    name_col.nullable = False
    name_col.primary_key = False
    name_col.unique = False
    name_col.default_value = None
    name_col.reference_table = None

    return [id_col, name_col]


@patch("forge_platform.routers.tables.tenant_service.get_tenant")
@patch("forge_platform.routers.tables.database_service.get_database")
@patch("forge_platform.services.table_service.get_table", return_value=None)
@patch("forge_platform.services.table_service.create_table")
def test_create_table(mock_create, mock_get_table, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    mock_create.return_value = (_mock_table_def(), _mock_columns())

    response = client.post(BASE_URL, json={"name": "customers", "columns": [{"name": "name", "type": "text", "nullable": False}]})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "customers"
    assert len(data["columns"]) == 2
    assert data["columns"][0]["name"] == "id"
    assert data["columns"][0]["primary_key"] is True


@patch("forge_platform.routers.tables.tenant_service.get_tenant")
@patch("forge_platform.routers.tables.database_service.get_database")
@patch("forge_platform.services.table_service.get_table")
def test_create_table_duplicate(mock_get_table, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    mock_get_table.return_value = (_mock_table_def(), _mock_columns())

    response = client.post(BASE_URL, json={"name": "customers", "columns": [{"name": "name", "type": "text"}]})
    assert response.status_code == 409


@patch("forge_platform.routers.tables.tenant_service.get_tenant", return_value=None)
def test_create_table_tenant_not_found(mock_get_tenant):
    response = client.post(BASE_URL, json={"name": "customers", "columns": [{"name": "name", "type": "text"}]})
    assert response.status_code == 404
    assert "Tenant not found" in response.json()["detail"]


def test_create_table_invalid_type():
    response = client.post(BASE_URL, json={"name": "customers", "columns": [{"name": "name", "type": "varchar"}]})
    assert response.status_code == 422


def test_create_table_reserved_name():
    response = client.post(BASE_URL, json={"name": "select", "columns": [{"name": "name", "type": "text"}]})
    assert response.status_code == 422


def test_create_table_reserved_column_name():
    response = client.post(BASE_URL, json={"name": "customers", "columns": [{"name": "table", "type": "text"}]})
    assert response.status_code == 422


@patch("forge_platform.routers.tables.tenant_service.get_tenant")
@patch("forge_platform.routers.tables.database_service.get_database")
@patch("forge_platform.services.table_service.list_tables", return_value=[])
def test_list_tables_empty(mock_list, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    response = client.get(BASE_URL)
    assert response.status_code == 200
    assert response.json() == {"tables": []}


@patch("forge_platform.routers.tables.tenant_service.get_tenant")
@patch("forge_platform.routers.tables.database_service.get_database")
@patch("forge_platform.services.table_service.get_table", return_value=None)
def test_get_table_not_found(mock_get_table, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    response = client.get(f"{BASE_URL}/customers")
    assert response.status_code == 404


@patch("forge_platform.routers.tables.tenant_service.get_tenant")
@patch("forge_platform.routers.tables.database_service.get_database")
@patch("forge_platform.services.table_service.alter_table")
def test_alter_table_add_column(mock_alter, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    cols = _mock_columns()
    phone_col = MagicMock()
    phone_col.name = "phone"
    phone_col.column_type = "text"
    phone_col.nullable = True
    phone_col.primary_key = False
    phone_col.unique = False
    phone_col.default_value = None
    phone_col.reference_table = None
    cols.append(phone_col)
    mock_alter.return_value = (_mock_table_def(), cols)

    response = client.put(f"{BASE_URL}/customers", json={"add_columns": [{"name": "phone", "type": "text"}]})
    assert response.status_code == 200
    assert len(response.json()["columns"]) == 3


@patch("forge_platform.routers.tables.tenant_service.get_tenant")
@patch("forge_platform.routers.tables.database_service.get_database")
@patch("forge_platform.services.table_service.alter_table")
def test_alter_table_drop_pk_column(mock_alter, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    mock_alter.side_effect = ValueError("Cannot drop primary key column 'id'")
    response = client.put(f"{BASE_URL}/customers", json={"drop_columns": ["id"]})
    assert response.status_code == 400
    assert "primary key" in response.json()["detail"]


@patch("forge_platform.routers.tables.tenant_service.get_tenant")
@patch("forge_platform.routers.tables.database_service.get_database")
@patch("forge_platform.services.table_service.delete_table")
def test_delete_table(mock_delete, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    td = _mock_table_def()
    td.status = "deleted"
    mock_delete.return_value = td
    response = client.delete(f"{BASE_URL}/customers")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"


@patch("forge_platform.routers.tables.tenant_service.get_tenant")
@patch("forge_platform.routers.tables.database_service.get_database")
@patch("forge_platform.services.table_service.delete_table", return_value=None)
def test_delete_table_not_found(mock_delete, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    response = client.delete(f"{BASE_URL}/nonexistent")
    assert response.status_code == 404
