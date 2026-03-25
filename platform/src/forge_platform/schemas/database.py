import re
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class DatabaseCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9_]*[a-z0-9]$", v) or len(v) < 2 or len(v) > 63:
            raise ValueError(
                "Name must be 2-63 characters, lowercase alphanumeric with underscores, "
                "starting with a letter and ending with alphanumeric"
            )
        return v


class DatabaseResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    pg_database: str
    pg_role: str
    secret_name: str
    status: str
    created_at: datetime


class DatabaseListResponse(BaseModel):
    databases: list[DatabaseResponse]


class DatabaseDeleteResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
