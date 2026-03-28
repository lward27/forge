import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class TenantLLMConfig(SQLModel, table=True):
    __tablename__ = "tenant_llm_config"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    provider_id: uuid.UUID = Field(foreign_key="llm_provider.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
