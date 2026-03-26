import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.errors import UniqueViolation
from sqlmodel import Session

from forge_platform.database import get_session
from forge_platform.schemas.row import (
    RowBatchCreate,
    RowBatchResponse,
    RowDeleteResponse,
    RowListResponse,
)
from forge_platform.services import database_service, row_service, tenant_service

router = APIRouter(
    prefix="/tenants/{tenant_id}/databases/{db_id}/tables/{table_name}/rows",
    tags=["rows"],
)


def _get_tenant_and_db(session: Session, tenant_id: uuid.UUID, db_id: uuid.UUID):
    tenant = tenant_service.get_tenant(session, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_db = database_service.get_database(session, tenant_id, db_id)
    if tenant_db is None:
        raise HTTPException(status_code=404, detail="Database not found")

    return tenant, tenant_db


@router.post("", status_code=201)
def create_row(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    body: dict,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    try:
        result = row_service.insert_row(session, tenant_db, table_name, body)
    except LookupError:
        raise HTTPException(status_code=404, detail="Table not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e.__cause__, UniqueViolation) or "UniqueViolation" in type(e).__name__:
            raise HTTPException(status_code=409, detail="Duplicate value for unique column")
        raise

    return result


@router.get("", response_model=RowListResponse)
def list_rows(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    filter: Optional[list[str]] = Query(None),
    sort: Optional[str] = Query(None),
    expand: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    try:
        rows, total = row_service.list_rows(
            session, tenant_db, table_name,
            filters=filter, sort=sort, limit=limit, offset=offset,
        )
        if expand:
            expand_cols = [c.strip() for c in expand.split(",")]
            rows = row_service.expand_rows(session, tenant_db, table_name, rows, expand_cols)
    except LookupError:
        raise HTTPException(status_code=404, detail="Table not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RowListResponse(rows=rows, total=total, limit=limit, offset=offset)


@router.get("/{pk}", response_model=dict)
def get_row(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    pk: int,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    try:
        result = row_service.get_row(session, tenant_db, table_name, pk)
    except LookupError:
        raise HTTPException(status_code=404, detail="Table not found")

    if result is None:
        raise HTTPException(status_code=404, detail="Row not found")

    return result


@router.put("/{pk}", response_model=dict)
def update_row(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    pk: int,
    body: dict,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    try:
        result = row_service.update_row(session, tenant_db, table_name, pk, body)
    except LookupError:
        raise HTTPException(status_code=404, detail="Table not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e.__cause__, UniqueViolation) or "UniqueViolation" in type(e).__name__:
            raise HTTPException(status_code=409, detail="Duplicate value for unique column")
        raise

    if result is None:
        raise HTTPException(status_code=404, detail="Row not found")

    return result


@router.delete("/{pk}", response_model=RowDeleteResponse)
def delete_row(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    pk: int,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    try:
        deleted = row_service.delete_row(session, tenant_db, table_name, pk)
    except LookupError:
        raise HTTPException(status_code=404, detail="Table not found")

    if not deleted:
        raise HTTPException(status_code=404, detail="Row not found")

    return RowDeleteResponse(id=pk, deleted=True)


@router.post("/batch", response_model=RowBatchResponse, status_code=201)
def create_rows_batch(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    body: RowBatchCreate,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    try:
        rows = row_service.insert_rows_batch(
            session, tenant_db, table_name, body.rows,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Table not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e.__cause__, UniqueViolation) or "UniqueViolation" in type(e).__name__:
            raise HTTPException(status_code=409, detail="Duplicate value for unique column")
        raise

    return RowBatchResponse(inserted=len(rows), rows=rows)


@router.get("/{pk}/related")
def get_related(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    pk: int,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    try:
        related = row_service.get_related_records(session, tenant_db, table_name, pk)
    except LookupError:
        raise HTTPException(status_code=404, detail="Table not found")

    return {"related": related}


@router.post("/bulk-delete")
def bulk_delete_rows(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    body: dict,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    ids = body.get("ids", [])
    if not ids or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="'ids' must be a non-empty list")

    try:
        deleted = row_service.bulk_delete_rows(session, tenant_db, table_name, ids)
    except LookupError:
        raise HTTPException(status_code=404, detail="Table not found")

    return {"deleted": deleted}
