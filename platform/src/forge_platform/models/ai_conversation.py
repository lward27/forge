import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON


class AIConversation(SQLModel, table=True):
    __tablename__ = "ai_conversation"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenant.id", index=True)
    database_id: uuid.UUID = Field(foreign_key="tenant_database.id")
    title: Optional[str] = Field(default=None)
    messages: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default=None)
