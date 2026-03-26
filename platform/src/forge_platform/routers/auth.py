import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from forge_platform.database import get_session
from forge_platform.middleware.auth import get_api_key
from forge_platform.schemas.auth import (
    ApiKeyCreate,
    ApiKeyListItem,
    ApiKeyListResponse,
    ApiKeyResponse,
)
from forge_platform.services import auth_service, tenant_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def get_me(
    session: Session = Depends(get_session),
    auth=Depends(get_api_key),
):
    """Return info about the current API key and its tenant."""
    if auth is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = {
        "role": auth.role,
        "key_name": auth.name,
        "key_prefix": auth.key_prefix,
        "tenant_id": str(auth.tenant_id) if auth.tenant_id else None,
        "tenant_name": None,
    }

    if auth.tenant_id:
        tenant = tenant_service.get_tenant(session, auth.tenant_id)
        if tenant:
            result["tenant_name"] = tenant.name

    return result


@router.post("/keys", response_model=ApiKeyResponse, status_code=201)
def create_key(
    body: ApiKeyCreate,
    session: Session = Depends(get_session),
    _auth=Depends(get_api_key),
):
    if body.role == "tenant" and body.tenant_id is None:
        raise HTTPException(
            status_code=400, detail="tenant_id required for tenant role keys"
        )

    if body.role == "admin" and body.tenant_id is not None:
        raise HTTPException(
            status_code=400, detail="tenant_id must not be set for admin keys"
        )

    api_key, plaintext = auth_service.create_api_key(
        session, name=body.name, role=body.role, tenant_id=body.tenant_id,
    )

    return ApiKeyResponse(
        id=api_key.id,
        key=plaintext,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        role=api_key.role,
        tenant_id=api_key.tenant_id,
        created_at=api_key.created_at,
    )


@router.get("/keys", response_model=ApiKeyListResponse)
def list_keys(
    session: Session = Depends(get_session),
    auth=Depends(get_api_key),
):
    # Tenant keys can only see their own keys
    if auth and auth.role == "tenant":
        keys = auth_service.list_keys(session, tenant_id=auth.tenant_id)
    else:
        keys = auth_service.list_keys(session)

    return ApiKeyListResponse(
        keys=[
            ApiKeyListItem(
                id=k.id,
                key_prefix=k.key_prefix,
                name=k.name,
                role=k.role,
                tenant_id=k.tenant_id,
                is_active=k.is_active,
                created_at=k.created_at,
                last_used_at=k.last_used_at,
            )
            for k in keys
        ]
    )


@router.delete("/keys/{key_id}")
def revoke_key(
    key_id: uuid.UUID,
    session: Session = Depends(get_session),
    _auth=Depends(get_api_key),
):
    api_key = auth_service.revoke_key(session, key_id)
    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")

    return {"id": str(api_key.id), "is_active": api_key.is_active}
