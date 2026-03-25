import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator
import re


class ResourceLimits(BaseModel):
    cpu: str = "2"
    memory: str = "4Gi"
    storage: str = "20Gi"


class TenantCreate(BaseModel):
    name: str
    display_name: str
    resource_limits: Optional[ResourceLimits] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$", v) or len(v) < 2 or len(v) > 63:
            raise ValueError(
                "Name must be 2-63 characters, lowercase alphanumeric with hyphens, "
                "starting with a letter and ending with alphanumeric"
            )
        if "--" in v:
            raise ValueError("Name must not contain consecutive hyphens")
        return v


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    namespace: str
    status: str
    resource_limits: dict
    created_at: datetime


class TenantDetailResponse(TenantResponse):
    resources: dict


class TenantListResponse(BaseModel):
    tenants: list[TenantResponse]


class TenantDeleteResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
