import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from forge_platform.database import get_session
from forge_platform.services import database_service, tenant_service, view_form_service

router = APIRouter(
    prefix="/tenants/{tenant_id}/databases/{db_id}/tables/{table_name}",
    tags=["views-forms"],
)


def _get_tenant_and_db(session, tenant_id, db_id):
    tenant = tenant_service.get_tenant(session, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant_db = database_service.get_database(session, tenant_id, db_id)
    if tenant_db is None:
        raise HTTPException(status_code=404, detail="Database not found")
    return tenant, tenant_db


# ── Views ──────────────────────────────────────────────

@router.get("/views")
def list_views(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    default: bool = Query(False),
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    if default:
        view = view_form_service.get_default_view(session, tenant_db.id, table_name)
        if view is None:
            raise HTTPException(status_code=404, detail="No default view found")
        return {"views": [_view_response(view)]}

    view = view_form_service.get_default_view(session, tenant_db.id, table_name)
    views = [_view_response(view)] if view else []
    return {"views": views}


@router.get("/views/{view_id}")
def get_view(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    view_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)
    view = view_form_service.get_view(session, view_id)
    if view is None or view.database_id != tenant_db.id or view.table_name != table_name:
        raise HTTPException(status_code=404, detail="View not found")
    return _view_response(view)


@router.put("/views/{view_id}")
def update_view(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    view_id: uuid.UUID,
    body: dict,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)
    view = view_form_service.get_view(session, view_id)
    if view is None or view.database_id != tenant_db.id or view.table_name != table_name:
        raise HTTPException(status_code=404, detail="View not found")

    config = body.get("config", body)
    updated = view_form_service.update_view(session, view_id, config)
    return _view_response(updated)


# ── Forms ──────────────────────────────────────────────

@router.get("/forms")
def list_forms(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    default: bool = Query(False),
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)

    if default:
        form = view_form_service.get_default_form(session, tenant_db.id, table_name)
        if form is None:
            raise HTTPException(status_code=404, detail="No default form found")
        return {"forms": [_form_response(form)]}

    form = view_form_service.get_default_form(session, tenant_db.id, table_name)
    forms = [_form_response(form)] if form else []
    return {"forms": forms}


@router.get("/forms/{form_id}")
def get_form(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    form_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)
    form = view_form_service.get_form(session, form_id)
    if form is None or form.database_id != tenant_db.id or form.table_name != table_name:
        raise HTTPException(status_code=404, detail="Form not found")
    return _form_response(form)


@router.put("/forms/{form_id}")
def update_form(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    table_name: str,
    form_id: uuid.UUID,
    body: dict,
    session: Session = Depends(get_session),
):
    _, tenant_db = _get_tenant_and_db(session, tenant_id, db_id)
    form = view_form_service.get_form(session, form_id)
    if form is None or form.database_id != tenant_db.id or form.table_name != table_name:
        raise HTTPException(status_code=404, detail="Form not found")

    config = body.get("config", body)
    updated = view_form_service.update_form(session, form_id, config)
    return _form_response(updated)


# ── Helpers ──────────────────────────────────────────────

def _view_response(view):
    return {
        "id": str(view.id),
        "table_name": view.table_name,
        "name": view.name,
        "is_default": view.is_default,
        "config": view.config,
        "created_at": view.created_at.isoformat() if view.created_at else None,
        "updated_at": view.updated_at.isoformat() if view.updated_at else None,
    }


def _form_response(form):
    return {
        "id": str(form.id),
        "table_name": form.table_name,
        "name": form.name,
        "is_default": form.is_default,
        "config": form.config,
        "created_at": form.created_at.isoformat() if form.created_at else None,
        "updated_at": form.updated_at.isoformat() if form.updated_at else None,
    }
