import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.evidence import Evidence


async def create_evidence(db: AsyncSession, **kwargs) -> Evidence:
    evidence = Evidence(**kwargs)
    db.add(evidence)
    await db.flush()
    await db.refresh(evidence)
    return evidence


async def list_evidence(
    db: AsyncSession,
    hypothesis_id: uuid.UUID,
    evidence_type: Optional[str] = None,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[Evidence], int]:
    base_filter = Evidence.hypothesis_id == hypothesis_id
    query = select(Evidence).where(base_filter)
    count_query = select(func.count(Evidence.id)).where(base_filter)
    if evidence_type:
        query = query.where(Evidence.evidence_type == evidence_type)
        count_query = count_query.where(Evidence.evidence_type == evidence_type)
    query = query.order_by(Evidence.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    count_result = await db.execute(count_query)
    return list(result.scalars().all()), count_result.scalar_one()
