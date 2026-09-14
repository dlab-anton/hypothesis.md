import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.hypothesis import Hypothesis
from ..db.models.evidence import Evidence
from ..db.models.event import Event


async def list_agents(db: AsyncSession, *, tenant_id: Optional[uuid.UUID] = None) -> list[dict]:
    """Aggregate unique created_by values across hypotheses, evidence, events."""
    # Hypotheses per agent (+ channels + timestamps)
    h_query = (
        select(
            Hypothesis.created_by,
            func.count(Hypothesis.id).label("count"),
            func.array_agg(distinct(Hypothesis.channel)).label("channels"),
            func.min(Hypothesis.created_at).label("first_seen"),
            func.max(Hypothesis.created_at).label("last_active"),
        )
        .where(Hypothesis.is_archived == False)  # noqa: E712
    )
    if tenant_id is not None:
        h_query = h_query.where(Hypothesis.tenant_id == tenant_id)
    h_query = h_query.group_by(Hypothesis.created_by)
    h_result = await db.execute(h_query)
    hyp_stats = {
        row.created_by: {
            "total_hypotheses": row.count,
            "channels": [c for c in (row.channels or []) if c is not None],
            "first_seen": row.first_seen,
            "last_active": row.last_active,
        }
        for row in h_result.all()
    }

    # Evidence per agent
    e_query = select(
        Evidence.created_by,
        func.count(Evidence.id).label("count"),
        func.min(Evidence.created_at).label("first_seen"),
        func.max(Evidence.created_at).label("last_active"),
    )
    if tenant_id is not None:
        e_query = e_query.join(Hypothesis, Evidence.hypothesis_id == Hypothesis.id)
        e_query = e_query.where(Hypothesis.tenant_id == tenant_id)
    e_query = e_query.group_by(Evidence.created_by)
    e_result = await db.execute(e_query)
    ev_stats = {
        row.created_by: {
            "total_evidence": row.count,
            "first_seen": row.first_seen,
            "last_active": row.last_active,
        }
        for row in e_result.all()
    }

    # Events per agent
    evt_query = select(
        Event.created_by,
        func.count(Event.id).label("count"),
        func.min(Event.created_at).label("first_seen"),
        func.max(Event.created_at).label("last_active"),
    )
    if tenant_id is not None:
        evt_query = evt_query.join(Hypothesis, Event.hypothesis_id == Hypothesis.id)
        evt_query = evt_query.where(Hypothesis.tenant_id == tenant_id)
    evt_query = evt_query.group_by(Event.created_by)
    evt_result = await db.execute(evt_query)
    event_stats = {
        row.created_by: {
            "total_events": row.count,
            "first_seen": row.first_seen,
            "last_active": row.last_active,
        }
        for row in evt_result.all()
    }

    # Merge all agents
    all_agents = set(hyp_stats) | set(ev_stats) | set(event_stats)
    agents = []
    for name in sorted(all_agents):
        h = hyp_stats.get(name, {"total_hypotheses": 0, "channels": [], "first_seen": None, "last_active": None})
        e = ev_stats.get(name, {"total_evidence": 0, "first_seen": None, "last_active": None})
        evt = event_stats.get(name, {"total_events": 0, "first_seen": None, "last_active": None})

        timestamps = [t for t in [h["first_seen"], e["first_seen"], evt["first_seen"]] if t]
        last_times = [t for t in [h["last_active"], e["last_active"], evt["last_active"]] if t]

        agents.append({
            "name": name,
            "total_hypotheses": h["total_hypotheses"],
            "total_evidence": e["total_evidence"],
            "total_events": evt["total_events"],
            "channels": h["channels"],
            "first_seen": min(timestamps) if timestamps else None,
            "last_active": max(last_times) if last_times else None,
        })

    return agents


async def agent_exists(db: AsyncSession, agent_name: str, *, tenant_id: Optional[uuid.UUID] = None) -> bool:
    """Check if an agent name exists in any table."""
    # Hypothesis: direct tenant filter
    h_query = select(func.count()).select_from(Hypothesis).where(Hypothesis.created_by == agent_name)
    if tenant_id is not None:
        h_query = h_query.where(Hypothesis.tenant_id == tenant_id)
    if (await db.execute(h_query)).scalar_one() > 0:
        return True

    # Evidence/Event: join through Hypothesis for tenant filter
    for model in [Evidence, Event]:
        q = select(func.count()).select_from(model).where(model.created_by == agent_name)
        if tenant_id is not None:
            q = q.join(Hypothesis, model.hypothesis_id == Hypothesis.id)
            q = q.where(Hypothesis.tenant_id == tenant_id)
        if (await db.execute(q)).scalar_one() > 0:
            return True
    return False


async def get_agent_activity(
    db: AsyncSession,
    agent_name: str,
    *,
    tenant_id: Optional[uuid.UUID] = None,
    limit: int = 20,
    since: Optional[datetime] = None,
) -> dict:
    """Recent activity for a specific agent."""
    # Recent hypotheses (exclude archived)
    h_query = (
        select(Hypothesis)
        .where(Hypothesis.created_by == agent_name)
        .where(Hypothesis.is_archived == False)  # noqa: E712
        .order_by(Hypothesis.created_at.desc())
        .limit(limit)
    )
    if tenant_id is not None:
        h_query = h_query.where(Hypothesis.tenant_id == tenant_id)
    if since:
        h_query = h_query.where(Hypothesis.created_at >= since)
    h_result = await db.execute(h_query)
    hypotheses = list(h_result.scalars().all())

    # Recent evidence (join for hypothesis statement — also filters by tenant)
    e_query = (
        select(Evidence, Hypothesis.statement)
        .join(Hypothesis, Evidence.hypothesis_id == Hypothesis.id)
        .where(Evidence.created_by == agent_name)
        .order_by(Evidence.created_at.desc())
        .limit(limit)
    )
    if tenant_id is not None:
        e_query = e_query.where(Hypothesis.tenant_id == tenant_id)
    if since:
        e_query = e_query.where(Evidence.created_at >= since)
    e_result = await db.execute(e_query)
    evidence = list(e_result.all())

    # Recent events (join for hypothesis statement — also filters by tenant)
    evt_query = (
        select(Event, Hypothesis.statement)
        .join(Hypothesis, Event.hypothesis_id == Hypothesis.id)
        .where(Event.created_by == agent_name)
        .order_by(Event.created_at.desc())
        .limit(limit)
    )
    if tenant_id is not None:
        evt_query = evt_query.where(Hypothesis.tenant_id == tenant_id)
    if since:
        evt_query = evt_query.where(Event.created_at >= since)
    evt_result = await db.execute(evt_query)
    events = list(evt_result.all())

    return {
        "hypotheses": hypotheses,
        "evidence": evidence,
        "events": events,
    }


async def get_inbox(
    db: AsyncSession,
    agent_name: str,
    *,
    tenant_id: Optional[uuid.UUID] = None,
    since: Optional[datetime] = None,
    channel: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list, int]:
    """
    Notifications for an agent: events on their hypotheses triggered by other agents.
    Returns (items, total_count).
    """
    base_filters = [
        Hypothesis.created_by == agent_name,
        Event.created_by != agent_name,
    ]
    if tenant_id is not None:
        base_filters.append(Hypothesis.tenant_id == tenant_id)
    if since:
        base_filters.append(Event.created_at >= since)
    if channel:
        base_filters.append(Hypothesis.channel == channel)

    # Count
    count_query = (
        select(func.count(Event.id))
        .join(Hypothesis, Event.hypothesis_id == Hypothesis.id)
        .where(*base_filters)
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Items
    items_query = (
        select(Event, Hypothesis.statement, Hypothesis.channel)
        .join(Hypothesis, Event.hypothesis_id == Hypothesis.id)
        .where(*base_filters)
        .order_by(Event.created_at.desc())
        .offset(offset)
        .limit(min(limit, 200))
    )
    result = await db.execute(items_query)
    items = list(result.all())

    return items, total
