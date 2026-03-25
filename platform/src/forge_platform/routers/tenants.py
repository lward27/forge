import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from forge_platform.database import get_session
from forge_platform.schemas.tenant import (
    TenantCreate,
    TenantDeleteResponse,
    TenantDetailResponse,
    TenantListResponse,
    TenantResponse,
)
from forge_platform.services import database_service, tenant_service

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=201)
def create_tenant(
    tenant_in: TenantCreate,
    session: Session = Depends(get_session),
):
    existing = tenant_service.get_tenant_by_name(session, tenant_in.name)
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Tenant '{tenant_in.name}' already exists"
        )

    tenant = tenant_service.create_tenant(session, tenant_in)
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        display_name=tenant.display_name,
        namespace=tenant.namespace,
        status=tenant.status,
        resource_limits=tenant.resource_limits,
        created_at=tenant.created_at,
    )


@router.get("", response_model=TenantListResponse)
def list_tenants(session: Session = Depends(get_session)):
    tenants = tenant_service.list_tenants(session)
    return TenantListResponse(
        tenants=[
            TenantResponse(
                id=t.id,
                name=t.name,
                display_name=t.display_name,
                namespace=t.namespace,
                status=t.status,
                resource_limits=t.resource_limits,
                created_at=t.created_at,
            )
            for t in tenants
        ]
    )


@router.get("/{tenant_id}", response_model=TenantDetailResponse)
def get_tenant(
    tenant_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    tenant = tenant_service.get_tenant(session, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return TenantDetailResponse(
        id=tenant.id,
        name=tenant.name,
        display_name=tenant.display_name,
        namespace=tenant.namespace,
        status=tenant.status,
        resource_limits=tenant.resource_limits,
        created_at=tenant.created_at,
        resources={
            "databases": database_service.count_databases(session, tenant.id),
            "services": 0,
            "frontends": 0,
        },
    )


@router.delete("/{tenant_id}", response_model=TenantDeleteResponse)
def delete_tenant(
    tenant_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    tenant = tenant_service.delete_tenant(session, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return TenantDeleteResponse(
        id=tenant.id,
        name=tenant.name,
        status=tenant.status,
    )
