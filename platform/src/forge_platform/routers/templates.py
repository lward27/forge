import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from forge_platform.database import get_session
from forge_platform.services import database_service, template_service, tenant_service
from forge_platform.templates import list_templates

router = APIRouter(tags=["templates"])


@router.get("/templates")
def get_templates():
    """List available templates."""
    return {"templates": list_templates()}


@router.post("/tenants/{tenant_id}/databases/{db_id}/deploy-template")
def deploy_template(
    tenant_id: uuid.UUID,
    db_id: uuid.UUID,
    body: dict,
    session: Session = Depends(get_session),
):
    tenant = tenant_service.get_tenant(session, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_db = database_service.get_database(session, tenant_id, db_id)
    if tenant_db is None:
        raise HTTPException(status_code=404, detail="Database not found")

    template_id = body.get("template_id")
    if not template_id:
        raise HTTPException(status_code=400, detail="'template_id' is required")

    try:
        result = template_service.deploy_template(session, tenant_db, template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result
