import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


# ── GET /agents ──────────────────────────────────────────────────

class AgentSummary(BaseModel):
    name: str
    total_hypotheses: int
    total_evidence: int
    total_events: int
    channels: list[str]
    first_seen: datetime
    last_active: datetime


class AgentListResponse(BaseModel):
    agents: list[AgentSummary]
    total: int


# ── GET /agents/{name}/activity ──────────────────────────────────

class AgentHypothesisSummary(BaseModel):
    id: uuid.UUID
    statement: str
    status: str
    confidence: Optional[float]
    channel: Optional[str]
    created_at: datetime


class AgentEvidenceSummary(BaseModel):
    id: uuid.UUID
    hypothesis_id: uuid.UUID
    hypothesis_statement: str
    evidence_type: str
    content: str
    created_at: datetime


class AgentEventSummary(BaseModel):
    id: uuid.UUID
    hypothesis_id: uuid.UUID
    hypothesis_statement: str
    event_type: str
    data: dict[str, Any]
    created_at: datetime


class AgentActivityResponse(BaseModel):
    agent: str
    hypotheses: list[AgentHypothesisSummary]
    evidence: list[AgentEvidenceSummary]
    events: list[AgentEventSummary]


# ── GET /inbox ───────────────────────────────────────────────────

class InboxItem(BaseModel):
    event_id: uuid.UUID
    hypothesis_id: uuid.UUID
    hypothesis_statement: str
    event_type: str
    data: dict[str, Any]
    triggered_by: str
    channel: Optional[str]
    created_at: datetime


class InboxResponse(BaseModel):
    agent: str
    items: list[InboxItem]
    total: int
    has_more: bool
    channel_goals: dict[str, str]
