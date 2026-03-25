import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from forge_platform.models.tenant import Tenant
from forge_platform.models.tenant_database import TenantDatabase
from forge_platform.schemas.database import DatabaseCreate
from forge_platform.services import kubernetes_service, postgres_service


PG_PREFIX = "forge_t"


def _pg_name(tenant_name: str, db_name: str) -> str:
    """Generate PG-safe name: forge_t_{tenant}_{db}"""
    sanitized_tenant = tenant_name.replace("-", "_")
    return f"{PG_PREFIX}_{sanitized_tenant}_{db_name}"


def create_database(session: Session, tenant: Tenant, db_in: DatabaseCreate) -> TenantDatabase:
    """Create a new database for a tenant."""
    pg_database = _pg_name(tenant.name, db_in.name)
    pg_role = f"{pg_database}_role"
    secret_name = f"forge-db-{db_in.name}"
    password = postgres_service.generate_password()

    # Create PG database and role
    postgres_service.create_database(pg_database, pg_role, password)

    # Create K8s Secret with connection info in tenant namespace
    secret_data = {
        "DATABASE_URL": (
            f"postgresql://{pg_role}:{password}"
            f"@forge-postgresql.forge-platform.svc.cluster.local:5432/{pg_database}"
        ),
        "POSTGRES_HOST": "forge-postgresql.forge-platform.svc.cluster.local",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": pg_database,
        "POSTGRES_USER": pg_role,
        "POSTGRES_PASSWORD": password,
    }
    kubernetes_service.create_secret(
        namespace=tenant.namespace,
        name=secret_name,
        data=secret_data,
        labels={
            "forge.lucas.engineering/tenant": tenant.name,
            "forge.lucas.engineering/managed-by": "forge-platform",
        },
    )

    # Persist to platform DB
    tenant_db = TenantDatabase(
        tenant_id=tenant.id,
        name=db_in.name,
        pg_database=pg_database,
        pg_role=pg_role,
        secret_name=secret_name,
    )
    session.add(tenant_db)
    session.commit()
    session.refresh(tenant_db)
    return tenant_db


def list_databases(session: Session, tenant_id: uuid.UUID) -> list[TenantDatabase]:
    """List all active databases for a tenant."""
    statement = select(TenantDatabase).where(
        TenantDatabase.tenant_id == tenant_id,
        TenantDatabase.status == "active",
    )
    return list(session.exec(statement).all())


def get_database(
    session: Session, tenant_id: uuid.UUID, db_id: uuid.UUID
) -> TenantDatabase | None:
    """Get a specific database by ID."""
    statement = select(TenantDatabase).where(
        TenantDatabase.id == db_id,
        TenantDatabase.tenant_id == tenant_id,
        TenantDatabase.status != "deleted",
    )
    return session.exec(statement).first()


def get_database_by_name(
    session: Session, tenant_id: uuid.UUID, name: str
) -> TenantDatabase | None:
    """Get a database by name within a tenant."""
    statement = select(TenantDatabase).where(
        TenantDatabase.tenant_id == tenant_id,
        TenantDatabase.name == name,
        TenantDatabase.status != "deleted",
    )
    return session.exec(statement).first()


def delete_database(
    session: Session, tenant: Tenant, db_id: uuid.UUID
) -> TenantDatabase | None:
    """Delete a tenant database, its PG database/role, and K8s Secret."""
    tenant_db = get_database(session, tenant.id, db_id)
    if tenant_db is None:
        return None

    tenant_db.status = "deleting"
    tenant_db.updated_at = datetime.now(timezone.utc)
    session.add(tenant_db)
    session.commit()

    # Drop PG database and role
    postgres_service.drop_database(tenant_db.pg_database, tenant_db.pg_role)

    # Delete K8s Secret
    kubernetes_service.delete_secret(
        namespace=tenant.namespace,
        name=tenant_db.secret_name,
    )

    tenant_db.status = "deleted"
    tenant_db.updated_at = datetime.now(timezone.utc)
    session.add(tenant_db)
    session.commit()
    session.refresh(tenant_db)
    return tenant_db


def count_databases(session: Session, tenant_id: uuid.UUID) -> int:
    """Count active databases for a tenant."""
    statement = select(TenantDatabase).where(
        TenantDatabase.tenant_id == tenant_id,
        TenantDatabase.status == "active",
    )
    return len(list(session.exec(statement).all()))
