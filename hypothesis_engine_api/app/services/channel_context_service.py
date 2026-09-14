import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.v1.endpoints import build_hypothesis_read
from ..core.auth_context import AuthContext
from ..core.exceptions import InvalidTransitionError, NotFoundError
from ..db.models.channel import Channel
from ..db.models.evidence import Evidence
from ..db.models.hypothesis import Hypothesis
from ..db.models.insight import Insight
from ..schemas.channel import ChannelRead
from ..schemas.channel_context import ChannelContextResponse, EvidencePage
from ..schemas.common import PaginatedResponse
from ..schemas.evidence import EvidenceRead
from ..schemas.insight import InsightRead

HYPOTHESIS_PAGE_LIMIT = 6
INSIGHT_PAGE_LIMIT = 20
EVIDENCE_PAGE_LIMIT = 20


async def _channel_for_request(
    db: AsyncSession,
    auth: AuthContext,
    *,
    name: str,
    expected_channel_id: uuid.UUID,
) -> Channel:
    if auth.is_master:
        query = select(Channel).where(
            Channel.id == expected_channel_id,
            Channel.name == name,
        )
    else:
        query = select(Channel).where(
            Channel.tenant_id == auth.require_tenant(),
            Channel.name == name,
        )

    channel = (await db.execute(query)).scalar_one_or_none()
    if channel is None:
        raise NotFoundError("Channel not found")
    if channel.id != expected_channel_id:
        raise InvalidTransitionError(
            detail="Channel identity does not match expected_channel_id",
            status_code=409,
        )
    return channel


async def _totals(
    db: AsyncSession, *, tenant_id: uuid.UUID, channel_name: str
) -> tuple[int, int, int]:
    active = (
        select(func.count(Hypothesis.id))
        .where(
            Hypothesis.tenant_id == tenant_id,
            Hypothesis.channel == channel_name,
            Hypothesis.is_archived.is_(False),
        )
        .scalar_subquery()
    )
    archived = (
        select(func.count(Hypothesis.id))
        .where(
            Hypothesis.tenant_id == tenant_id,
            Hypothesis.channel == channel_name,
            Hypothesis.is_archived.is_(True),
        )
        .scalar_subquery()
    )
    insights = (
        select(func.count(Insight.id))
        .where(Insight.tenant_id == tenant_id, Insight.channel == channel_name)
        .scalar_subquery()
    )
    row = (await db.execute(select(active, archived, insights))).one()
    return int(row[0]), int(row[1]), int(row[2])


async def _hypotheses(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel_name: str,
    archived: bool,
    offset: int,
) -> list[Hypothesis]:
    result = await db.execute(
        select(Hypothesis)
        .where(
            Hypothesis.tenant_id == tenant_id,
            Hypothesis.channel == channel_name,
            Hypothesis.is_archived.is_(archived),
        )
        .order_by(Hypothesis.updated_at.desc(), Hypothesis.id.desc())
        .offset(offset)
        .limit(HYPOTHESIS_PAGE_LIMIT)
    )
    return list(result.scalars().all())


async def _insights(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel_name: str,
    offset: int,
) -> list[Insight]:
    result = await db.execute(
        select(Insight)
        .where(Insight.tenant_id == tenant_id, Insight.channel == channel_name)
        .order_by(Insight.updated_at.desc(), Insight.id.desc())
        .offset(offset)
        .limit(INSIGHT_PAGE_LIMIT)
    )
    return list(result.scalars().all())


async def _evidence(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel_name: str,
    hypothesis_ids: list[uuid.UUID],
) -> tuple[dict[uuid.UUID, list[EvidenceRead]], dict[uuid.UUID, dict[str, int]]]:
    items: dict[uuid.UUID, list[EvidenceRead]] = {item_id: [] for item_id in hypothesis_ids}
    counts: dict[uuid.UUID, dict[str, int]] = {
        item_id: {"supporting": 0, "contradicting": 0, "neutral": 0, "total": 0}
        for item_id in hypothesis_ids
    }
    if not hypothesis_ids:
        return items, counts

    scope = (
        Hypothesis.id.in_(hypothesis_ids),
        Hypothesis.tenant_id == tenant_id,
        Hypothesis.channel == channel_name,
    )
    grouped = (
        select(
            Evidence.hypothesis_id.label("hypothesis_id"),
            func.count(Evidence.id).label("total"),
            func.count(Evidence.id)
            .filter(Evidence.evidence_type == "supporting")
            .label("supporting"),
            func.count(Evidence.id)
            .filter(Evidence.evidence_type == "contradicting")
            .label("contradicting"),
            func.count(Evidence.id)
            .filter(Evidence.evidence_type == "neutral")
            .label("neutral"),
        )
        .join(Hypothesis, Hypothesis.id == Evidence.hypothesis_id)
        .where(*scope)
        .group_by(Evidence.hypothesis_id)
        .cte("evidence_counts")
    )
    ranked = (
        select(
            *Evidence.__table__.c,
            func.row_number()
            .over(
                partition_by=Evidence.hypothesis_id,
                order_by=(Evidence.created_at.desc(), Evidence.id.desc()),
            )
            .label("page_row"),
        )
        .join(Hypothesis, Hypothesis.id == Evidence.hypothesis_id)
        .where(*scope)
        .cte("ranked_evidence")
    )
    query = (
        select(
            ranked,
            grouped.c.total,
            grouped.c.supporting,
            grouped.c.contradicting,
            grouped.c.neutral,
        )
        .join(grouped, grouped.c.hypothesis_id == ranked.c.hypothesis_id)
        .where(ranked.c.page_row <= EVIDENCE_PAGE_LIMIT)
        .order_by(
            ranked.c.hypothesis_id,
            ranked.c.created_at.desc(),
            ranked.c.id.desc(),
        )
    )
    for row in (await db.execute(query)).mappings():
        hypothesis_id = row["hypothesis_id"]
        counts[hypothesis_id] = {
            "supporting": int(row["supporting"]),
            "contradicting": int(row["contradicting"]),
            "neutral": int(row["neutral"]),
            "total": int(row["total"]),
        }
        items[hypothesis_id].append(
            EvidenceRead(
                id=row["id"],
                hypothesis_id=hypothesis_id,
                content=row["content"],
                source=row["source"],
                evidence_type=row["evidence_type"],
                strength=row["strength"],
                confidence_after=row["confidence_after"],
                created_by=row["created_by"],
                created_at=row["created_at"],
            )
        )
    return items, counts


async def read_channel_context(
    db: AsyncSession,
    auth: AuthContext,
    *,
    name: str,
    expected_channel_id: uuid.UUID,
    active_offset: int,
    archived_offset: int,
    insight_offset: int,
) -> ChannelContextResponse:
    channel = await _channel_for_request(
        db, auth, name=name, expected_channel_id=expected_channel_id
    )
    tenant_id = channel.tenant_id
    active_total, archived_total, insight_total = await _totals(
        db, tenant_id=tenant_id, channel_name=channel.name
    )
    active = await _hypotheses(
        db,
        tenant_id=tenant_id,
        channel_name=channel.name,
        archived=False,
        offset=active_offset,
    )
    archived = await _hypotheses(
        db,
        tenant_id=tenant_id,
        channel_name=channel.name,
        archived=True,
        offset=archived_offset,
    )
    insights = await _insights(
        db,
        tenant_id=tenant_id,
        channel_name=channel.name,
        offset=insight_offset,
    )
    hypotheses = [*active, *archived]
    hypothesis_ids = [hypothesis.id for hypothesis in hypotheses]
    evidence, counts = await _evidence(
        db,
        tenant_id=tenant_id,
        channel_name=channel.name,
        hypothesis_ids=hypothesis_ids,
    )

    return ChannelContextResponse(
        channel=ChannelRead.from_model(channel),
        active_hypotheses=PaginatedResponse(
            items=[build_hypothesis_read(item, counts[item.id]) for item in active],
            total=active_total,
            offset=active_offset,
            limit=HYPOTHESIS_PAGE_LIMIT,
        ),
        archived_hypotheses=PaginatedResponse(
            items=[build_hypothesis_read(item, counts[item.id]) for item in archived],
            total=archived_total,
            offset=archived_offset,
            limit=HYPOTHESIS_PAGE_LIMIT,
        ),
        insights=PaginatedResponse(
            items=[InsightRead.from_model(item) for item in insights],
            total=insight_total,
            offset=insight_offset,
            limit=INSIGHT_PAGE_LIMIT,
        ),
        evidence_pages=[
            EvidencePage(
                hypothesis_id=hypothesis.id,
                items=evidence[hypothesis.id],
                total=counts[hypothesis.id]["total"],
            )
            for hypothesis in hypotheses
        ],
    )
