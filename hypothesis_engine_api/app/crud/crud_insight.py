import uuid
from typing import Any, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.insight import Insight


async def create_insight(
    db: AsyncSession,
    *,
    channel: str,
    insight_type: str,
    content: str,
    created_by: str,
    metadata: Optional[dict[str, Any]] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> Insight:
    # Channel already normalized by schema validator — pass through as-is
    insight = Insight(
        channel=channel,
        insight_type=insight_type,
        content=content,
        created_by=created_by,
        metadata_=metadata,
        tenant_id=tenant_id,
    )
    db.add(insight)
    await db.flush()
    await db.refresh(insight)
    return insight


async def get_insight(
    db: AsyncSession, insight_id: uuid.UUID, *, tenant_id: Optional[uuid.UUID] = None,
) -> Optional[Insight]:
    query = select(Insight).where(Insight.id == insight_id)
    if tenant_id is not None:
        query = query.where(Insight.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def list_insights(
    db: AsyncSession,
    channel: Optional[str] = None,
    insight_type: Optional[str] = None,
    created_by: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    tenant_id: Optional[uuid.UUID] = None,
) -> tuple[list[Insight], int]:
    filters = []
    if tenant_id is not None:
        filters.append(Insight.tenant_id == tenant_id)
    if channel:
        # Channel already normalized by schema/endpoint — match as-is
        filters.append(Insight.channel == channel.lower().strip())
    if insight_type:
        filters.append(Insight.insight_type == insight_type)
    if created_by:
        filters.append(Insight.created_by == created_by)

    query = select(Insight)
    count_query = select(func.count(Insight.id))
    if filters:
        where_clause = and_(*filters)
        query = query.where(where_clause)
        count_query = count_query.where(where_clause)
    query = query.order_by(Insight.updated_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    count_result = await db.execute(count_query)
    return list(result.scalars().all()), count_result.scalar_one()


async def update_insight(
    db: AsyncSession,
    insight: Insight,
    *,
    content: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    updated_by: str,
) -> Insight:
    if content is not None:
        insight.content = content
    if metadata is not None:
        insight.metadata_ = metadata
    insight.updated_by = updated_by
    await db.flush()
    await db.refresh(insight)
    return insight


async def delete_insight(db: AsyncSession, insight: Insight) -> None:
    await db.delete(insight)
    await db.flush()
