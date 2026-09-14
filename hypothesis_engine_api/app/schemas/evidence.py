from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from ..core.constants import EvidenceType
from .common import validate_created_by


class EvidenceCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    source: Optional[str] = Field(None, max_length=500)
    evidence_type: EvidenceType
    strength: Optional[float] = Field(None, ge=0.0, le=1.0)
    created_by: str = Field(..., min_length=1, max_length=255)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Optionally update hypothesis confidence")
    expected_channel_id: uuid.UUID | SkipJsonSchema[None] = Field(
        None,
        description=(
            "Optional current channel identity precondition. New evidence is added only when "
            "the locked hypothesis still belongs to this channel."
        ),
    )

    @field_validator("created_by")
    @classmethod
    def validate_created_by_field(cls, v: str) -> str:
        result = validate_created_by(v)
        if result is None:
            raise ValueError("created_by is required")
        return result

    @model_validator(mode="after")
    def reject_null_expected_channel_id(self) -> "EvidenceCreate":
        if "expected_channel_id" in self.model_fields_set and self.expected_channel_id is None:
            raise ValueError("expected_channel_id must be a UUID when provided")
        return self


class EvidenceRead(BaseModel):
    id: uuid.UUID
    hypothesis_id: uuid.UUID
    content: str
    source: Optional[str]
    evidence_type: EvidenceType
    strength: Optional[float]
    confidence_after: Optional[float] = None
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EvidenceCreateResponse(BaseModel):
    """Response for POST /evidence — returns both the new evidence and the updated hypothesis."""
    evidence: EvidenceRead
    hypothesis: HypothesisRead


# Deferred import to avoid circular dependency at module load time
from .hypothesis import HypothesisRead  # noqa: E402

EvidenceCreateResponse.model_rebuild()
