import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from ..core.constants import HypothesisStatus, RelationshipType
from .common import validate_json_size, validate_created_by


class RelationshipCreate(BaseModel):
    target_hypothesis_id: uuid.UUID = Field(..., description="The hypothesis to relate to")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    created_by: str = Field(..., min_length=1, max_length=255)
    metadata: Optional[dict[str, Any]] = Field(None, description="Optional context for why these are related")

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


class RelationshipRead(BaseModel):
    id: uuid.UUID
    source_hypothesis_id: uuid.UUID
    target_hypothesis_id: uuid.UUID
    relationship_type: RelationshipType
    created_by: str
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, rel) -> "RelationshipRead":
        return cls(
            id=rel.id,
            source_hypothesis_id=rel.source_hypothesis_id,
            target_hypothesis_id=rel.target_hypothesis_id,
            relationship_type=rel.relationship_type,
            created_by=rel.created_by,
            metadata=rel.metadata_,
            created_at=rel.created_at,
        )


# Network graph response
class NetworkNode(BaseModel):
    id: uuid.UUID
    statement: str
    status: HypothesisStatus
    confidence: Optional[float] = None
    created_by: str


class NetworkEdge(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    relationship_type: RelationshipType
    created_by: str


class NetworkResponse(BaseModel):
    root_id: uuid.UUID
    nodes: list[NetworkNode]
    edges: list[NetworkEdge]
