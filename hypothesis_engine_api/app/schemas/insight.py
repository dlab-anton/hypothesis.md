import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from ..core.constants import InsightType
from .common import validate_json_size, validate_created_by, normalize_channel


class InsightCreate(BaseModel):
    channel: str = Field(..., min_length=1, max_length=100, description="Domain scope (auto-normalized lowercase)")
    insight_type: InsightType = Field(..., description="Type of insight")
    content: str = Field(..., min_length=1, max_length=10000, description="The insight in natural language")
    created_by: str = Field(..., min_length=1, max_length=255)
    metadata: Optional[dict[str, Any]] = Field(None, description="Structured data (calibration numbers, hypothesis references, etc.)")

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

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        return normalize_channel(v) or v


class InsightUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=10000, description="Updated insight text")
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


class InsightRead(BaseModel):
    id: uuid.UUID
    channel: str
    insight_type: InsightType
    content: str
    created_by: str
    updated_by: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, insight) -> "InsightRead":
        return cls(
            id=insight.id,
            channel=insight.channel,
            insight_type=insight.insight_type,
            content=insight.content,
            created_by=insight.created_by,
            updated_by=insight.updated_by,
            metadata=insight.metadata_,
            created_at=insight.created_at,
            updated_at=insight.updated_at,
        )
