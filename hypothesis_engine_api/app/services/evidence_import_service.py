import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import InvalidTransitionError, NotFoundError
from ..db.models.channel import Channel
from ..db.models.hypothesis import Hypothesis


async def lock_evidence_target(
    db: AsyncSession,
    hypothesis_id: uuid.UUID,
    *,
    tenant_id: uuid.UUID | None,
    expected_channel_id: uuid.UUID | None,
) -> Hypothesis:
    """Lock a target and, when requested, its current channel before insertion."""
    query = select(Hypothesis).where(Hypothesis.id == hypothesis_id)
    if tenant_id is not None:
        query = query.where(Hypothesis.tenant_id == tenant_id)
    hypothesis = (await db.execute(
        query.with_for_update().execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if hypothesis is None:
        raise NotFoundError(f"Hypothesis {hypothesis_id} not found")

    if expected_channel_id is not None:
        channel_id = await db.scalar(
            select(Channel.id)
            .where(
                Channel.id == expected_channel_id,
                Channel.tenant_id == hypothesis.tenant_id,
                Channel.name == hypothesis.channel,
            )
            # Concurrent imports may share a channel. This row lock only needs
            # to prevent rename/deletion until the target evidence commits.
            .with_for_update(read=True)
        )
        if channel_id is None:
            raise InvalidTransitionError(
                detail="Hypothesis channel does not match expected_channel_id",
                status_code=409,
            )

    return hypothesis
