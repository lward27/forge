import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class TenantDatabase(SQLModel, table=True):
    __tablename__ = "tenant_database"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    name: str
    pg_database: str = Field(unique=True)
    pg_role: str = Field(unique=True)
    secret_name: str
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default=None)
