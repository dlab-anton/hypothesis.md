import uuid
from typing import Any, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.channel import Channel


async def create_channel(
    db: AsyncSession,
    *,
    name: str,
    goal: str,
    created_by: str,
    metadata: Optional[dict[str, Any]] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> Channel:
    channel = Channel(
        name=name,
        goal=goal,
        created_by=created_by,
        metadata_=metadata,
        tenant_id=tenant_id,
    )
    db.add(channel)
    await db.flush()
    await db.refresh(channel)
    return channel


async def get_channel_by_name(
    db: AsyncSession, name: str, *, tenant_id: Optional[uuid.UUID] = None,
) -> Optional[Channel]:
    query = select(Channel).where(Channel.name == name)
    if tenant_id is not None:
        query = query.where(Channel.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def list_channels(
    db: AsyncSession,
    offset: int = 0,
    limit: int = 50,
    tenant_id: Optional[uuid.UUID] = None,
) -> tuple[list[Channel], int]:
    filters = []
    if tenant_id is not None:
        filters.append(Channel.tenant_id == tenant_id)

    query = select(Channel)
    count_query = select(func.count(Channel.id))
    if filters:
        where_clause = and_(*filters)
        query = query.where(where_clause)
        count_query = count_query.where(where_clause)
    query = query.order_by(Channel.name.asc()).offset(offset).limit(limit)

    result = await db.execute(query)
    count_result = await db.execute(count_query)
    return list(result.scalars().all()), count_result.scalar_one()


async def update_channel(
    db: AsyncSession,
    channel: Channel,
    *,
    goal: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    updated_by: str,
) -> Channel:
    if goal is not None:
        channel.goal = goal
    if metadata is not None:
        channel.metadata_ = metadata
    channel.updated_by = updated_by
    await db.flush()
    await db.refresh(channel)
    return channel


async def delete_channel(db: AsyncSession, channel: Channel) -> None:
    await db.delete(channel)
    await db.flush()
