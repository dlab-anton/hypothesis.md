import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from .common import validate_json_size, validate_created_by, normalize_channel


class ChannelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Channel name (auto-normalized lowercase)")
    goal: str = Field(..., min_length=1, max_length=5000, description="What this channel is for")
    created_by: str = Field(..., min_length=1, max_length=255)
    metadata: Optional[dict[str, Any]] = Field(None, description="Structured data")

    @field_validator("created_by")
    @classmethod
    def validate_created_by_field(cls, v: str) -> str:
        result = validate_created_by(v)
        if result is None:
            raise ValueError("created_by is required")
        return result

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_json_fields(cls, v: dict | None) -> dict | None:
        return validate_json_size(v)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return normalize_channel(v) or v


class ChannelUpdate(BaseModel):
    goal: Optional[str] = Field(None, min_length=1, max_length=5000, description="Updated goal")
    metadata: Optional[dict[str, Any]] = Field(None, description="Updated structured data")
    updated_by: str = Field(..., min_length=1, max_length=255, description="Who is making this update")

    @field_validator("updated_by")
    @classmethod
    def validate_updated_by_field(cls, v: str) -> str:
        result = validate_created_by(v)
        if result is None:
            raise ValueError("updated_by is required")
        return result

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_json_fields(cls, v: dict | None) -> dict | None:
        return validate_json_size(v)


class ChannelRead(BaseModel):
    id: uuid.UUID
    name: str
    goal: str
    created_by: str
    updated_by: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, channel) -> "ChannelRead":
        return cls(
            id=channel.id,
            name=channel.name,
            goal=channel.goal,
            created_by=channel.created_by,
            updated_by=channel.updated_by,
            metadata=channel.metadata_,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )
