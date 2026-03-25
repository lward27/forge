import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class ColumnDefinition(SQLModel, table=True):
    __tablename__ = "column_definition"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    table_id: uuid.UUID = Field(foreign_key="table_definition.id", index=True)
    name: str
    column_type: str
    nullable: bool = Field(default=True)
    primary_key: bool = Field(default=False)
    unique: bool = Field(default=False)
    default_value: Optional[str] = Field(default=None)
    ordinal: int = Field(default=0)
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
