import uuid
from typing import Literal

from pydantic import BaseModel, Field

from .channel import ChannelRead
from .common import PaginatedResponse
from .evidence import EvidenceRead
from .hypothesis import HypothesisRead
from .insight import InsightRead


class EvidencePage(BaseModel):
    hypothesis_id: uuid.UUID
    items: list[EvidenceRead] = Field(max_length=20)
    total: int = Field(ge=0)
    offset: Literal[0] = 0
    limit: Literal[20] = 20


class ChannelContextResponse(BaseModel):
    format: Literal["hypothesis.channel-context.v1"] = (
        "hypothesis.channel-context.v1"
    )
    channel: ChannelRead
    active_hypotheses: PaginatedResponse[HypothesisRead]
    archived_hypotheses: PaginatedResponse[HypothesisRead]
    insights: PaginatedResponse[InsightRead]
    evidence_pages: list[EvidencePage] = Field(max_length=12)
