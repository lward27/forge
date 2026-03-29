import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class TableDefinition(SQLModel, table=True):
    __tablename__ = "table_definition"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    database_id: uuid.UUID = Field(foreign_key="tenant_database.id", index=True)
    name: str
    display_field: Optional[str] = Field(default=None)
    app_name: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default=None)
