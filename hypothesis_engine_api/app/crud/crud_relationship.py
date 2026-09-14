import uuid
from typing import Any, Optional

from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.relationship import Relationship
from ..db.models.hypothesis import Hypothesis


async def create_relationship(
    db: AsyncSession,
    *,
    source_hypothesis_id: uuid.UUID,
    target_hypothesis_id: uuid.UUID,
    relationship_type: str,
    created_by: str,
    metadata: Optional[dict[str, Any]] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> Relationship:
    rel = Relationship(
        source_hypothesis_id=source_hypothesis_id,
        target_hypothesis_id=target_hypothesis_id,
        relationship_type=relationship_type,
        created_by=created_by,
        metadata_=metadata,
        tenant_id=tenant_id,
    )
    db.add(rel)
    await db.flush()
    await db.refresh(rel)
    return rel


async def get_relationship(
    db: AsyncSession, relationship_id: uuid.UUID, *, tenant_id: Optional[uuid.UUID] = None,
) -> Optional[Relationship]:
    query = select(Relationship).where(Relationship.id == relationship_id)
    if tenant_id is not None:
        query = query.where(Relationship.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def list_relationships(
    db: AsyncSession,
    hypothesis_id: uuid.UUID,
    relationship_type: Optional[str] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> list[Relationship]:
    """Get all relationships where hypothesis is source OR target."""
    filters = [
        or_(
            Relationship.source_hypothesis_id == hypothesis_id,
            Relationship.target_hypothesis_id == hypothesis_id,
        )
    ]
    if relationship_type:
        filters.append(Relationship.relationship_type == relationship_type)
    if tenant_id is not None:
        filters.append(Relationship.tenant_id == tenant_id)

    result = await db.execute(
        select(Relationship)
        .where(and_(*filters))
        .order_by(Relationship.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_relationship(db: AsyncSession, relationship: Relationship) -> None:
    await db.delete(relationship)
    await db.flush()


async def check_duplicate(
    db: AsyncSession,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    relationship_type: str,
    tenant_id: Optional[uuid.UUID] = None,
) -> bool:
    """Check if this relationship already exists.

    For symmetric types (competes_with), checks both directions —
    H1→H2 and H2→H1 are the same relationship.
    """
    from ..core.constants import SYMMETRIC_RELATIONSHIP_TYPES

    conditions = [
        and_(
            Relationship.source_hypothesis_id == source_id,
            Relationship.target_hypothesis_id == target_id,
            Relationship.relationship_type == relationship_type,
        )
    ]

    if relationship_type in SYMMETRIC_RELATIONSHIP_TYPES:
        conditions.append(
            and_(
                Relationship.source_hypothesis_id == target_id,
                Relationship.target_hypothesis_id == source_id,
                Relationship.relationship_type == relationship_type,
            )
        )

    query = select(func.count()).select_from(Relationship).where(or_(*conditions))
    if tenant_id is not None:
        query = query.where(Relationship.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalar_one() > 0


_MAX_BFS_NODES = 200  # Safety cap to prevent runaway traversals


async def get_network(
    db: AsyncSession,
    hypothesis_id: uuid.UUID,
    max_depth: int = 10,
    tenant_id: Optional[uuid.UUID] = None,
) -> tuple[list[Hypothesis], list[Relationship]]:
    """BFS walk from a hypothesis, collecting all connected nodes and edges."""
    visited_ids: set[uuid.UUID] = set()
    queue: list[uuid.UUID] = [hypothesis_id]
    all_hypotheses: list[Hypothesis] = []
    all_relationships: list[Relationship] = []
    seen_rel_ids: set[uuid.UUID] = set()
    depth = 0

    while queue and depth < max_depth:
        # Deduplicate and cap the batch
        batch_ids = []
        for h_id in queue:
            if h_id not in visited_ids and len(visited_ids) + len(batch_ids) < _MAX_BFS_NODES:
                if h_id not in batch_ids:
                    batch_ids.append(h_id)
        queue = []

        if not batch_ids:
            break

        visited_ids.update(batch_ids)

        # Batch-fetch all hypotheses for this depth level
        h_q = select(Hypothesis).where(Hypothesis.id.in_(batch_ids))
        if tenant_id is not None:
            h_q = h_q.where(Hypothesis.tenant_id == tenant_id)
        h_result = await db.execute(h_q)
        all_hypotheses.extend(h_result.scalars().all())

        # Batch-fetch all relationships touching this batch
        rel_q = select(Relationship).where(
            or_(
                Relationship.source_hypothesis_id.in_(batch_ids),
                Relationship.target_hypothesis_id.in_(batch_ids),
            )
        )
        if tenant_id is not None:
            rel_q = rel_q.where(Relationship.tenant_id == tenant_id)
        rel_result = await db.execute(rel_q)
        for rel in rel_result.scalars().all():
            if rel.id not in seen_rel_ids:
                seen_rel_ids.add(rel.id)
                all_relationships.append(rel)

            # Queue neighbours not yet visited
            for candidate in (rel.source_hypothesis_id, rel.target_hypothesis_id):
                if candidate not in visited_ids:
                    queue.append(candidate)

        depth += 1

    return all_hypotheses, all_relationships
