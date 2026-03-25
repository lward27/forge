import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class ApiKeyCreate(BaseModel):
    name: str
    role: str
    tenant_id: Optional[uuid.UUID] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "tenant"):
            raise ValueError("Role must be 'admin' or 'tenant'")
        return v


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    key: str  # plaintext, returned only on creation
    key_prefix: str
    name: str
    role: str
    tenant_id: Optional[uuid.UUID]
    created_at: datetime


class ApiKeyListItem(BaseModel):
    id: uuid.UUID
    key_prefix: str
    name: str
    role: str
    tenant_id: Optional[uuid.UUID]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyListItem]
