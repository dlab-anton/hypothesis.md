import uuid
from typing import Literal

from pydantic import BaseModel, Field

from .channel import ChannelRead
from .evidence import EvidenceRead
from .hypothesis import HypothesisRead


class TargetedEvidencePage(BaseModel):
    hypothesis_id: uuid.UUID
    items: list[EvidenceRead] = Field(max_length=20)
    total: int = Field(ge=0)
    offset: int = Field(ge=0, le=100_000)
    limit: Literal[20] = 20


class HypothesisContextResponse(BaseModel):
    format: Literal["hypothesis.hypothesis-context.v1"] = (
        "hypothesis.hypothesis-context.v1"
    )
    channel: ChannelRead
    hypothesis: HypothesisRead
    evidence_page: TargetedEvidencePage
