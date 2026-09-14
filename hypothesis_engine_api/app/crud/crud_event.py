import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.event import Event


async def create_event(db: AsyncSession, **kwargs) -> Event:
    event = Event(**kwargs)
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


async def list_events(
    db: AsyncSession,
    hypothesis_id: uuid.UUID,
    offset: int = 0,
    limit: int = 100,
) -> list[Event]:
    query = (
        select(Event)
        .where(Event.hypothesis_id == hypothesis_id)
        .order_by(Event.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())
