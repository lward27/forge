import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from forge_platform.database import get_session
from forge_platform.services import dashboard_service, database_service, tenant_service

router = APIRouter(
    prefix="/tenants/{tenant_id}/databases/{db_id}/dashboards",
    tags=["dashboards"],
)


def _get_tenant_and_db(session, tenant_id, db_id):
    tenant = tenant_service.get_tenant(session, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant_db = database_service.get_database(session, tenant_id, db_id)
    if tenant_db is None:
        raise HTTPException(status_code=404, detail="Database not found")
    return tenant, tenant_db


def _dashboard_response(d):
    return {
        "id": str(d.id),
        "database_id": str(d.database_id),
        "name": d.name,
        "is_default": d.is_default,
        "config": d.config,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


@router.post("", status_code=201)
def create_dashboard(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    body: dict,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="'name' is required")

    d = dashboard_service.create_dashboard(
        session,
        database_id=tenant_db.id,
        name=name,
        is_default=body.get("is_default", False),
        config=body.get("config"),
    )
    return _dashboard_response(d)


@router.get("")
def list_dashboards(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)
    dashboards = dashboard_service.list_dashboards(session, tenant_db.id)
    return {"dashboards": [_dashboard_response(d) for d in dashboards]}


@router.get("/{dashboard_id}")
def get_dashboard(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)
    d = dashboard_service.get_dashboard(session, dashboard_id)
    if d is None or d.database_id != tenant_db.id:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return _dashboard_response(d)


@router.put("/{dashboard_id}")
def update_dashboard(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    body: dict,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)
    d = dashboard_service.get_dashboard(session, dashboard_id)
    if d is None or d.database_id != tenant_db.id:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    updated = dashboard_service.update_dashboard(
        session,
        dashboard_id,
        name=body.get("name"),
        is_default=body.get("is_default"),
        config=body.get("config"),
    )
    return _dashboard_response(updated)


@router.delete("/{dashboard_id}")
def delete_dashboard(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)
    d = dashboard_service.get_dashboard(session, dashboard_id)
    if d is None or d.database_id != tenant_db.id:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    dashboard_service.delete_dashboard(session, dashboard_id)
    return {"deleted": True}
