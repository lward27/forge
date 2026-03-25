import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from forge_platform.database import get_session
from forge_platform.schemas.database import (
    DatabaseCreate,
    DatabaseDeleteResponse,
    DatabaseListResponse,
    DatabaseResponse,
)
from forge_platform.services import database_service, tenant_service

router = APIRouter(prefix="/tenants/{tenant_id}/databases", tags=["databases"])


def _get_tenant_or_404(session: Session, tenant_id: uuid.UUID):
    tenant = tenant_service.get_tenant(session, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.post("", response_model=DatabaseResponse, status_code=201)
def create_database(
    tenant_id: uuid.UUID,
    db_in: DatabaseCreate,
    session: Session = Depends(get_session),
):
    tenant = _get_tenant_or_404(session, tenant_id)

    existing = database_service.get_database_by_name(session, tenant.id, db_in.name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Database '{db_in.name}' already exists for this tenant",
        )

    tenant_db = database_service.create_database(session, tenant, db_in)
    return DatabaseResponse(
        id=tenant_db.id,
        tenant_id=tenant_db.tenant_id,
        name=tenant_db.name,
        pg_database=tenant_db.pg_database,
        pg_role=tenant_db.pg_role,
        secret_name=tenant_db.secret_name,
        status=tenant_db.status,
        created_at=tenant_db.created_at,
    )


@router.get("", response_model=DatabaseListResponse)
def list_databases(
    tenant_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    _get_tenant_or_404(session, tenant_id)

    databases = database_service.list_databases(session, tenant_id)
    return DatabaseListResponse(
        databases=[
            DatabaseResponse(
                id=db.id,
                tenant_id=db.tenant_id,
                name=db.name,
                pg_database=db.pg_database,
                pg_role=db.pg_role,
                secret_name=db.secret_name,
                status=db.status,
                created_at=db.created_at,
            )
            for db in databases
        ]
    )


@router.get("/{db_id}", response_model=DatabaseResponse)
def get_database(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    _get_tenant_or_404(session, tenant_id)

    tenant_db = database_service.get_database(session, tenant_id, db_id)
    if tenant_db is None:
        raise HTTPException(status_code=404, detail="Database not found")

    return DatabaseResponse(
        id=tenant_db.id,
        tenant_id=tenant_db.tenant_id,
        name=tenant_db.name,
        pg_database=tenant_db.pg_database,
        pg_role=tenant_db.pg_role,
        secret_name=tenant_db.secret_name,
        status=tenant_db.status,
        created_at=tenant_db.created_at,
    )


@router.delete("/{db_id}", response_model=DatabaseDeleteResponse)
def delete_database(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    tenant = _get_tenant_or_404(session, tenant_id)

    tenant_db = database_service.delete_database(session, tenant, db_id)
    if tenant_db is None:
        raise HTTPException(status_code=404, detail="Database not found")

    return DatabaseDeleteResponse(
        id=tenant_db.id,
        name=tenant_db.name,
        status=tenant_db.status,
    )
