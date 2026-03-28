import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Text


class LLMProvider(SQLModel, table=True):
    __tablename__ = "llm_provider"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    api_url: str
    api_key_encrypted: str = Field(sa_column=Column(Text))
    model: str
    pricing_input: float = Field(default=0.0)  # cost per 1M input tokens
    pricing_output: float = Field(default=0.0)  # cost per 1M output tokens
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
