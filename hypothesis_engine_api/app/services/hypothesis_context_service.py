import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.v1.endpoints import build_hypothesis_read
from ..core.auth_context import AuthContext
from ..core.exceptions import NotFoundError
from ..db.models.evidence import Evidence
from ..db.models.hypothesis import Hypothesis
from ..schemas.channel import ChannelRead
from ..schemas.evidence import EvidenceRead
from ..schemas.hypothesis_context import (
    HypothesisContextResponse,
    TargetedEvidencePage,
)
from .channel_context_service import _channel_for_request

EVIDENCE_PAGE_LIMIT = 20


async def _hypothesis_for_request(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel_name: str,
    hypothesis_id: uuid.UUID,
) -> Hypothesis | None:
    return (
        await db.execute(
            select(Hypothesis).where(
                Hypothesis.id == hypothesis_id,
                Hypothesis.tenant_id == tenant_id,
                Hypothesis.channel == channel_name,
            )
        )
    ).scalar_one_or_none()


async def _evidence_counts(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel_name: str,
    hypothesis_id: uuid.UUID,
) -> tuple[int, dict[str, int]]:
    scope = (
        Hypothesis.id == hypothesis_id,
        Hypothesis.tenant_id == tenant_id,
        Hypothesis.channel == channel_name,
    )
    row = (
        await db.execute(
            select(
                func.count(Evidence.id),
                func.count(Evidence.id).filter(Evidence.evidence_type == "supporting"),
                func.count(Evidence.id).filter(
                    Evidence.evidence_type == "contradicting"
                ),
                func.count(Evidence.id).filter(Evidence.evidence_type == "neutral"),
            )
            .join(Hypothesis, Hypothesis.id == Evidence.hypothesis_id)
            .where(*scope)
        )
    ).one()
    return int(row[0]), {
        "supporting": int(row[1]),
        "contradicting": int(row[2]),
        "neutral": int(row[3]),
    }


async def _evidence_page(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel_name: str,
    hypothesis_id: uuid.UUID,
    evidence_offset: int,
) -> list[Evidence]:
    scope = (
        Hypothesis.id == hypothesis_id,
        Hypothesis.tenant_id == tenant_id,
        Hypothesis.channel == channel_name,
    )
    return list(
        (
            await db.execute(
                select(Evidence)
                .join(Hypothesis, Hypothesis.id == Evidence.hypothesis_id)
                .where(*scope)
                .order_by(Evidence.created_at.desc(), Evidence.id.desc())
                .offset(evidence_offset)
                .limit(EVIDENCE_PAGE_LIMIT)
            )
        ).scalars().all()
    )


async def read_hypothesis_context(
    db: AsyncSession,
    auth: AuthContext,
    *,
    name: str,
    expected_channel_id: uuid.UUID,
    hypothesis_id: uuid.UUID,
    evidence_offset: int,
) -> HypothesisContextResponse:
    channel = await _channel_for_request(
        db, auth, name=name, expected_channel_id=expected_channel_id
    )
    hypothesis = await _hypothesis_for_request(
        db,
        tenant_id=channel.tenant_id,
        channel_name=channel.name,
        hypothesis_id=hypothesis_id,
    )
    if hypothesis is None:
        raise NotFoundError("Hypothesis not found")

    total, counts = await _evidence_counts(
        db,
        tenant_id=channel.tenant_id,
        channel_name=channel.name,
        hypothesis_id=hypothesis_id,
    )
    page = await _evidence_page(
        db,
        tenant_id=channel.tenant_id,
        channel_name=channel.name,
        hypothesis_id=hypothesis_id,
        evidence_offset=evidence_offset,
    )

    return HypothesisContextResponse(
        channel=ChannelRead.from_model(channel),
        hypothesis=build_hypothesis_read(hypothesis, counts),
        evidence_page=TargetedEvidencePage(
            hypothesis_id=hypothesis.id,
            items=[EvidenceRead.model_validate(item) for item in page],
            total=total,
            offset=evidence_offset,
        ),
    )
