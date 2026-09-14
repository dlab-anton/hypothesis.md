import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from ..core.constants import HypothesisStatus
from .common import (
    MAX_TAGS, MAX_TAG_LENGTH, validate_json_size, validate_created_by,
    validate_tags, normalize_channel,
)


class EvidenceCounts(BaseModel):
    supporting: int = 0
    contradicting: int = 0
    neutral: int = 0


_CREATION_STATUSES = frozenset({HypothesisStatus.DRAFT, HypothesisStatus.ACTIVE})


class HypothesisCreate(BaseModel):
    statement: str = Field(..., min_length=1, max_length=2000)
    context: Optional[str] = Field(None, max_length=5000)
    falsification_criteria: Optional[str] = Field(None, max_length=5000, description="What evidence would disprove this hypothesis?")
    status: HypothesisStatus = HypothesisStatus.DRAFT
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    initial_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence at creation time (auto-set from confidence if omitted). Immutable after creation.")
    tags: list[str] = Field(default_factory=list)
    created_by: str = Field(..., min_length=1, max_length=255)
    deadline: Optional[datetime] = Field(None, description="When should this hypothesis be resolved by?")
    metadata: Optional[dict] = Field(None, description="Domain-specific structured data (e.g. ticker, target_price)")
    null_hypothesis: Optional[str] = Field(None, max_length=2000, description="H0: The default assumption to reject (e.g. 'ACME will NOT reach $5')")
    experimental_design: Optional[dict] = Field(None, description="Structured experiment plan: variables, controls, data sources, success criteria")
    significance_level: Optional[float] = Field(None, ge=0.0, le=1.0, description="Alpha level for rejecting H0 (e.g. 0.05)")
    outcome: Optional[dict] = Field(None, description="Structured result when concluded: actual vs predicted, effect size, narrative")
    channel: Optional[str] = Field(None, max_length=100, description="Channel/category (e.g. stock-predictions, debugging)")

    @field_validator("status")
    @classmethod
    def validate_creation_status(cls, v: HypothesisStatus) -> HypothesisStatus:
        if v not in _CREATION_STATUSES:
            raise ValueError(f"New hypotheses can only start as 'draft' or 'active', got '{v}'")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags_field(cls, v: list[str]) -> list[str]:
        return validate_tags(v) or []

    @field_validator("created_by")
    @classmethod
    def validate_created_by_field(cls, v: str) -> str:
        result = validate_created_by(v)
        if result is None:
            raise ValueError("created_by is required")
        return result

    @field_validator("metadata", "experimental_design", "outcome", mode="before")
    @classmethod
    def validate_json_fields(cls, v: dict | None) -> dict | None:
        return validate_json_size(v)

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str | None) -> str | None:
        return normalize_channel(v)


class HypothesisUpdate(BaseModel):
    statement: Optional[str] = Field(None, min_length=1, max_length=2000)
    context: Optional[str] = Field(None, max_length=5000)
    falsification_criteria: Optional[str] = Field(None, max_length=5000)
    status: Optional[HypothesisStatus] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    tags: Optional[list[str]] = None
    is_archived: Optional[bool] = None
    created_by: Optional[str] = Field(None, min_length=1, max_length=255)
    deadline: Optional[datetime] = None
    metadata: Optional[dict] = None
    null_hypothesis: Optional[str] = Field(None, max_length=2000)
    experimental_design: Optional[dict] = None
    significance_level: Optional[float] = Field(None, ge=0.0, le=1.0)
    outcome: Optional[dict] = None
    channel: Optional[str] = Field(None, max_length=100)

    @field_validator("tags")
    @classmethod
    def validate_tags_field(cls, v: list[str] | None) -> list[str] | None:
        return validate_tags(v)

    @field_validator("created_by")
    @classmethod
    def validate_created_by_field(cls, v: str | None) -> str | None:
        return validate_created_by(v)

    @field_validator("metadata", "experimental_design", "outcome", mode="before")
    @classmethod
    def validate_json_fields(cls, v: dict | None) -> dict | None:
        return validate_json_size(v)

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str | None) -> str | None:
        return normalize_channel(v)


class HypothesisRead(BaseModel):
    id: uuid.UUID
    statement: str
    context: Optional[str]
    falsification_criteria: Optional[str]
    status: HypothesisStatus
    confidence: Optional[float]
    initial_confidence: Optional[float] = None
    tags: list[str]
    created_by: str
    parent_id: Optional[uuid.UUID]
    is_archived: bool
    evidence_counts: EvidenceCounts
    deadline: Optional[datetime]
    metadata: Optional[dict]
    null_hypothesis: Optional[str]
    experimental_design: Optional[dict]
    significance_level: Optional[float]
    outcome: Optional[dict]
    channel: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HypothesisRevise(BaseModel):
    statement: str = Field(..., min_length=1, max_length=2000)
    context: Optional[str] = Field(None, max_length=5000)
    falsification_criteria: Optional[str] = Field(None, max_length=5000, description="What evidence would disprove the revised hypothesis?")
    rationale: str = Field(..., min_length=1, max_length=5000, description="Why is this hypothesis being revised? What evidence or reasoning prompted the change?")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    created_by: str = Field(..., min_length=1, max_length=255)
    deadline: Optional[datetime] = None
    metadata: Optional[dict] = None
    null_hypothesis: Optional[str] = Field(None, max_length=2000, description="H0 for the revised hypothesis")
    experimental_design: Optional[dict] = Field(None, description="Updated experiment plan for the revision")
    significance_level: Optional[float] = Field(None, ge=0.0, le=1.0)
    channel: Optional[str] = Field(None, max_length=100)

    @field_validator("tags")
    @classmethod
    def validate_tags_field(cls, v: list[str]) -> list[str]:
        return validate_tags(v) or []

    @field_validator("created_by")
    @classmethod
    def validate_created_by_field(cls, v: str) -> str:
        result = validate_created_by(v)
        if result is None:
            raise ValueError("created_by is required")
        return result

    @field_validator("metadata", "experimental_design", mode="before")
    @classmethod
    def validate_json_fields(cls, v: dict | None) -> dict | None:
        return validate_json_size(v)

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str | None) -> str | None:
        return normalize_channel(v)


class LineageResponse(BaseModel):
    chain: list[HypothesisRead]
    current_id: uuid.UUID
