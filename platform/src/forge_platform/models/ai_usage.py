import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class AIUsage(SQLModel, table=True):
    __tablename__ = "ai_usage"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    provider_id: uuid.UUID = Field(foreign_key="llm_provider.id")
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    cost_input: float = Field(default=0.0)
    cost_output: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
