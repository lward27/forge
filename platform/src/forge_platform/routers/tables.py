import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from forge_platform.database import get_session
from forge_platform.schemas.table import (
    ColumnResponse,
    TableAlter,
    TableCreate,
    TableDeleteResponse,
    TableListResponse,
    TableResponse,
)
from forge_platform.services import database_service, table_service, tenant_service

router = APIRouter(
    prefix="/tenants/{tenant_id}/databases/{db_id}/tables",
    tags=["tables"],
)


def _get_tenant_and_db(session: Session, tenant_id: uuid.UUID, db_id: uuid.UUID):
    tenant = tenant_service.get_tenant(session, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_db = database_service.get_database(session, tenant_id, db_id)
    if tenant_db is None:
        raise HTTPException(status_code=404, detail="Database not found")

    return tenant, tenant_db


def _table_response(table_def, columns, database_id) -> TableResponse:
    return TableResponse(
        name=table_def.name,
        database_id=database_id,
        columns=[
            ColumnResponse(
                name=c.name,
                type=c.column_type,
                nullable=c.nullable,
                primary_key=c.primary_key,
                unique=c.unique,
                default=c.default_value,
            )
            for c in columns
        ],
        created_at=table_def.created_at,
    )


@router.post("", response_model=TableResponse, status_code=201)
def create_table(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_in: TableCreate,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    existing = table_service.get_table(session, tenant_db.id, table_in.name)
    if existing is not None:
        raise HTTPException(
            status_code=409, detail=f"Table '{table_in.name}' already exists"
        )

    table_def, columns = table_service.create_table(session, tenant_db, table_in)
    return _table_response(table_def, columns, tenant_db.id)


@router.get("", response_model=TableListResponse)
def list_tables(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    tables = table_service.list_tables(session, tenant_db.id)
    return TableListResponse(
        tables=[_table_response(t, cols, tenant_db.id) for t, cols in tables]
    )


@router.get("/{table_name}", response_model=TableResponse)
def get_table(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    result = table_service.get_table(session, tenant_db.id, table_name)
    if result is None:
        raise HTTPException(status_code=404, detail="Table not found")

    table_def, columns = result
    return _table_response(table_def, columns, tenant_db.id)


@router.put("/{table_name}", response_model=TableResponse)
def alter_table(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    alter_in: TableAlter,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    try:
        result = table_service.alter_table(session, tenant_db, table_name, alter_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if result is None:
        raise HTTPException(status_code=404, detail="Table not found")

    table_def, columns = result
    return _table_response(table_def, columns, tenant_db.id)


@router.delete("/{table_name}", response_model=TableDeleteResponse)
def delete_table(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    table_def = table_service.delete_table(session, tenant_db, table_name)
    if table_def is None:
        raise HTTPException(status_code=404, detail="Table not found")

    return TableDeleteResponse(name=table_def.name, status=table_def.status)
