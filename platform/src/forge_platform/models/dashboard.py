import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON


class Dashboard(SQLModel, table=True):
    __tablename__ = "dashboard"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    database_id: uuid.UUID = Field(foreign_key="tenant_database.id", index=True)
    name: str
    is_default: bool = Field(default=False)
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default=None)
