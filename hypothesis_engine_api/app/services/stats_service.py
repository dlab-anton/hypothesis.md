import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.hypothesis import Hypothesis
from ..db.models.evidence import Evidence
from ..schemas.common import StatsResponse


async def get_stats(db: AsyncSession, *, tenant_id: Optional[uuid.UUID] = None) -> StatsResponse:
    base = [Hypothesis.is_archived == False]  # noqa: E712
    if tenant_id is not None:
        base.append(Hypothesis.tenant_id == tenant_id)
    base_filter = and_(*base)

    total_result = await db.execute(
        select(func.count(Hypothesis.id)).where(base_filter)
    )
    total = total_result.scalar_one()

    status_result = await db.execute(
        select(Hypothesis.status, func.count(Hypothesis.id))
        .where(base_filter)
        .group_by(Hypothesis.status)
    )
    by_status = {status: count for status, count in status_result.all()}

    avg_result = await db.execute(
        select(func.avg(Hypothesis.confidence))
        .where(base_filter)
        .where(Hypothesis.confidence.isnot(None))
    )
    avg_confidence = avg_result.scalar_one()
    if avg_confidence is not None:
        avg_confidence = round(float(avg_confidence), 3)

    ev_query = select(func.count(Evidence.id))
    if tenant_id is not None:
        ev_query = ev_query.join(Hypothesis, Evidence.hypothesis_id == Hypothesis.id)
        ev_query = ev_query.where(Hypothesis.tenant_id == tenant_id)
    evidence_result = await db.execute(ev_query)
    total_evidence = evidence_result.scalar_one()

    tags_result = await db.execute(
        select(func.unnest(Hypothesis.tags).label("tag"), func.count().label("cnt"))
        .where(base_filter)
        .group_by("tag")
        .order_by(func.count().desc())
        .limit(10)
    )
    top_tags = [{"tag": tag, "count": count} for tag, count in tags_result.all()]

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_result = await db.execute(
        select(func.count(Hypothesis.id))
        .where(base_filter)
        .where(Hypothesis.created_at >= seven_days_ago)
    )
    recent_count = recent_result.scalar_one()

    return StatsResponse(
        total=total,
        by_status=by_status,
        avg_confidence=avg_confidence,
        total_evidence=total_evidence,
        top_tags=top_tags,
        recent_count_7d=recent_count,
    )
