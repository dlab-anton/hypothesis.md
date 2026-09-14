import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .common import validate_label


class ApiKeyCreate(BaseModel):
    label: Optional[str] = Field(None, max_length=255, description="Optional name for this key")
    tenant_id: Optional[uuid.UUID] = Field(
        None,
        description="Create a key in an existing workspace using an active same-workspace key or master authority. Omit to create a new workspace.",
    )

    @field_validator("label")
    @classmethod
    def validate_label_field(cls, v: str | None) -> str | None:
        return validate_label(v)


class ApiKeyGenerated(BaseModel):
    """Returned once on creation. The full key is never shown again."""
    key: str = Field(..., description="The API key (shown once, store it safely)")
    prefix: str = Field(..., description="Key prefix for identification")
    label: Optional[str] = None
    tenant_id: uuid.UUID = Field(..., description="Workspace identifier; not an authentication credential")
    created_at: datetime


class ApiKeyInfo(BaseModel):
    """Admin view of a key (no secret material)."""
    id: uuid.UUID
    prefix: str
    label: Optional[str] = None
    tenant_id: uuid.UUID
    is_active: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, api_key) -> "ApiKeyInfo":
        return cls(
            id=api_key.id,
            prefix=api_key.key_prefix,
            label=api_key.label,
            tenant_id=api_key.tenant_id,
            is_active=api_key.is_active,
            last_used_at=api_key.last_used_at,
            created_at=api_key.created_at,
        )
