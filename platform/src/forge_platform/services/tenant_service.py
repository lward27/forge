import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from forge_platform.models.tenant import Tenant
from forge_platform.schemas.tenant import TenantCreate, ResourceLimits
from forge_platform.services import kubernetes_service


NAMESPACE_PREFIX = "forge-tenant-"


def create_tenant(session: Session, tenant_in: TenantCreate) -> Tenant:
    """Create a new tenant with its Kubernetes namespace."""
    resource_limits = tenant_in.resource_limits or ResourceLimits()
    limits_dict = resource_limits.model_dump()
    namespace = f"{NAMESPACE_PREFIX}{tenant_in.name}"

    tenant = Tenant(
        name=tenant_in.name,
        display_name=tenant_in.display_name,
        namespace=namespace,
        resource_limits=limits_dict,
    )

    # Create k8s resources first — if this fails, we don't persist to DB
    kubernetes_service.create_tenant_namespace(
        name=tenant_in.name,
        resource_limits=limits_dict,
    )

    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


def list_tenants(session: Session) -> list[Tenant]:
    """List all active tenants."""
    statement = select(Tenant).where(Tenant.status == "active")
    return list(session.exec(statement).all())


def get_tenant(session: Session, tenant_id: uuid.UUID) -> Tenant | None:
    """Get a tenant by ID."""
    statement = select(Tenant).where(
        Tenant.id == tenant_id, Tenant.status != "deleted"
    )
    return session.exec(statement).first()


def get_tenant_by_name(session: Session, name: str) -> Tenant | None:
    """Get a tenant by name."""
    statement = select(Tenant).where(Tenant.name == name, Tenant.status != "deleted")
    return session.exec(statement).first()


def delete_tenant(session: Session, tenant_id: uuid.UUID) -> Tenant | None:
    """Delete a tenant and its Kubernetes namespace."""
    tenant = get_tenant(session, tenant_id)
    if tenant is None:
        return None

    tenant.status = "deleting"
    tenant.updated_at = datetime.now(timezone.utc)
    session.add(tenant)
    session.commit()

    # Delete k8s namespace (cascades all resources in it)
    kubernetes_service.delete_tenant_namespace(tenant.namespace)

    tenant.status = "deleted"
    tenant.updated_at = datetime.now(timezone.utc)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant
