from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ....api.deps import get_db_session
from ....core.auth_context import AuthContext
from ....core.security import get_api_key
from ....core.exceptions import NotFoundError
from ....core.rate_limit import limiter
from ....crud import crud_agent, crud_channel
from ....schemas.agent import (
    AgentSummary,
    AgentListResponse,
    AgentActivityResponse,
    AgentHypothesisSummary,
    AgentEvidenceSummary,
    AgentEventSummary,
    InboxItem,
    InboxResponse,
)

router = APIRouter(tags=["agents"])


@router.get("/agents", response_model=AgentListResponse, summary="List agents")
async def list_agents(
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    """List all known agents with summary stats."""
    agents = await crud_agent.list_agents(db, tenant_id=auth.tenant_id)
    return AgentListResponse(
        agents=[AgentSummary(**a) for a in agents],
        total=len(agents),
    )


@router.get("/agents/{agent_name}/activity", response_model=AgentActivityResponse, summary="Get agent activity")
async def get_agent_activity(
    agent_name: str = Path(..., min_length=1, max_length=255),
    limit: int = Query(20, ge=1, le=100),
    since: Optional[datetime] = Query(None, description="Only show activity after this datetime"),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    """Get recent activity for a specific agent."""
    raw = await crud_agent.get_agent_activity(db, agent_name, tenant_id=auth.tenant_id, limit=limit, since=since)

    # If no activity returned, check if agent exists at all
    if not raw["hypotheses"] and not raw["evidence"] and not raw["events"]:
        if not await crud_agent.agent_exists(db, agent_name, tenant_id=auth.tenant_id):
            raise NotFoundError(f"Agent '{agent_name}' not found")

    hypotheses = [
        AgentHypothesisSummary(
            id=h.id,
            statement=h.statement,
            status=h.status,
            confidence=h.confidence,
            channel=h.channel,
            created_at=h.created_at,
        )
        for h in raw["hypotheses"]
    ]

    evidence = [
        AgentEvidenceSummary(
            id=ev.id,
            hypothesis_id=ev.hypothesis_id,
            hypothesis_statement=stmt,
            evidence_type=ev.evidence_type,
            content=ev.content,
            created_at=ev.created_at,
        )
        for ev, stmt in raw["evidence"]
    ]

    events = [
        AgentEventSummary(
            id=evt.id,
            hypothesis_id=evt.hypothesis_id,
            hypothesis_statement=stmt,
            event_type=evt.event_type,
            data=evt.data,
            created_at=evt.created_at,
        )
        for evt, stmt in raw["events"]
    ]

    return AgentActivityResponse(
        agent=agent_name,
        hypotheses=hypotheses,
        evidence=evidence,
        events=events,
    )


@router.get(
    "/agents/{agent_name}/status",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/markdown": {}}}},
    summary="Get agent status report",
)
@limiter.limit("10/minute")
async def get_agent_status(
    request: Request,
    agent_name: str = Path(..., min_length=1, max_length=255),
    channel: Optional[str] = Query(None, description="Filter report to a single channel"),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    """Full heartbeat status report for an agent in markdown format."""
    if not await crud_agent.agent_exists(db, agent_name, tenant_id=auth.tenant_id):
        raise NotFoundError(f"Agent '{agent_name}' not found")

    from ....services.status_service import generate_status_report

    markdown = await generate_status_report(
        db, agent_name, tenant_id=auth.tenant_id, channel=channel,
    )
    return PlainTextResponse(content=markdown, media_type="text/markdown")


@router.get("/inbox", response_model=InboxResponse, summary="Get agent inbox")
async def get_inbox(
    agent: str = Query(..., min_length=1, max_length=255, description="Agent name to get inbox for"),
    since: Optional[datetime] = Query(None, description="Only show notifications after this datetime"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    """
    Get notifications for an agent: events on their hypotheses triggered by other agents.
    Self-actions are excluded. Supports polling via 'since' parameter.
    """
    items, total = await crud_agent.get_inbox(
        db, agent, tenant_id=auth.tenant_id, since=since, channel=channel, limit=limit, offset=offset,
    )

    inbox_items = [
        InboxItem(
            event_id=evt.id,
            hypothesis_id=evt.hypothesis_id,
            hypothesis_statement=stmt,
            event_type=evt.event_type,
            data=evt.data,
            triggered_by=evt.created_by,
            channel=hyp_channel,
            created_at=evt.created_at,
        )
        for evt, stmt, hyp_channel in items
    ]

    # Collect channel goals for all channels referenced in inbox items
    channel_names = {item.channel for item in inbox_items if item.channel}
    channel_goals: dict[str, str] = {}
    for ch_name in channel_names:
        ch = await crud_channel.get_channel_by_name(db, ch_name, tenant_id=auth.tenant_id)
        if ch and ch.goal:
            channel_goals[ch_name] = ch.goal

    return InboxResponse(
        agent=agent,
        items=inbox_items,
        total=total,
        has_more=(offset + limit) < total,
        channel_goals=channel_goals,
    )
