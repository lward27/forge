from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from forge_platform.app import app
from forge_platform.schemas.row import parse_filter, VALID_OPERATORS

import tests.conftest  # noqa: F401

client = TestClient(app)

TENANT_ID = "00000000-0000-0000-0000-000000000001"
DB_ID = "00000000-0000-0000-0000-000000000002"
BASE_URL = f"/tenants/{TENANT_ID}/databases/{DB_ID}/tables/customers/rows"


def _mock_tenant():
    t = MagicMock()
    t.id = TENANT_ID
    t.name = "test-app"
    t.status = "active"
    return t


def _mock_db():
    db = MagicMock()
    db.id = DB_ID
    db.tenant_id = TENANT_ID
    db.pg_database = "forge_t_test_app_mydb"
    db.pg_role = "forge_t_test_app_mydb_role"
    db.status = "active"
    return db


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.insert_row")
def test_create_row(mock_insert, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    mock_insert.return_value = {"id": 1, "name": "Alice", "email": "a@b.com"}
    response = client.post(BASE_URL, json={"name": "Alice", "email": "a@b.com"})
    assert response.status_code == 201
    assert response.json()["id"] == 1


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.insert_row")
def test_create_row_validation_error(mock_insert, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    mock_insert.side_effect = ValueError("Column 'name' is required")
    response = client.post(BASE_URL, json={"email": "a@b.com"})
    assert response.status_code == 400
    assert "required" in response.json()["detail"]


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.insert_row")
def test_create_row_table_not_found(mock_insert, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    mock_insert.side_effect = LookupError("Table not found")
    response = client.post(BASE_URL, json={"name": "Alice"})
    assert response.status_code == 404


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.list_rows")
def test_list_rows(mock_list, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    mock_list.return_value = ([{"id": 1, "name": "Alice"}], 1)
    response = client.get(BASE_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["rows"]) == 1


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.list_rows")
def test_list_rows_with_pagination(mock_list, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    mock_list.return_value = ([{"id": 2, "name": "Bob"}], 5)
    response = client.get(f"{BASE_URL}?limit=1&offset=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert data["limit"] == 1
    assert data["offset"] == 1


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.get_row")
def test_get_row(mock_get, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    mock_get.return_value = {"id": 1, "name": "Alice"}
    response = client.get(f"{BASE_URL}/1")
    assert response.status_code == 200
    assert response.json()["name"] == "Alice"


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.get_row", return_value=None)
def test_get_row_not_found(mock_get, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    response = client.get(f"{BASE_URL}/999")
    assert response.status_code == 404


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.update_row")
def test_update_row(mock_update, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    mock_update.return_value = {"id": 1, "name": "Alice Updated"}
    response = client.put(f"{BASE_URL}/1", json={"name": "Alice Updated"})
    assert response.status_code == 200
    assert response.json()["name"] == "Alice Updated"


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.update_row", return_value=None)
def test_update_row_not_found(mock_update, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    response = client.put(f"{BASE_URL}/999", json={"name": "Nope"})
    assert response.status_code == 404


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.delete_row", return_value=True)
def test_delete_row(mock_delete, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    response = client.delete(f"{BASE_URL}/1")
    assert response.status_code == 200
    assert response.json()["deleted"] is True


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.delete_row", return_value=False)
def test_delete_row_not_found(mock_delete, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    response = client.delete(f"{BASE_URL}/999")
    assert response.status_code == 404


@patch("forge_platform.routers.rows.tenant_service.get_tenant")
@patch("forge_platform.routers.rows.database_service.get_database")
@patch("forge_platform.services.row_service.insert_rows_batch")
def test_batch_insert(mock_batch, mock_get_db, mock_get_tenant):
    mock_get_tenant.return_value = _mock_tenant()
    mock_get_db.return_value = _mock_db()
    mock_batch.return_value = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    response = client.post(f"{BASE_URL}/batch", json={"rows": [{"name": "Alice"}, {"name": "Bob"}]})
    assert response.status_code == 201
    data = response.json()
    assert data["inserted"] == 2


def test_parse_filter_valid():
    f = parse_filter("name:eq:Alice")
    assert f.column == "name"
    assert f.operator == "eq"
    assert f.value == "Alice"


def test_parse_filter_with_colons_in_value():
    f = parse_filter("url:eq:http://example.com")
    assert f.value == "http://example.com"


def test_parse_filter_invalid_format():
    try:
        parse_filter("invalid")
        assert False
    except ValueError as e:
        assert "Invalid filter format" in str(e)


def test_parse_filter_invalid_operator():
    try:
        parse_filter("name:badop:value")
        assert False
    except ValueError as e:
        assert "Invalid operator" in str(e)


def test_all_operators_mapped():
    assert len(VALID_OPERATORS) == 9
