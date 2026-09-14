import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, and_, or_, literal_column, union_all, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.hypothesis import Hypothesis
from ..db.models.evidence import Evidence


async def create_hypothesis(db: AsyncSession, **kwargs) -> Hypothesis:
    # Map schema field 'metadata' to model attribute 'metadata_'
    if "metadata" in kwargs:
        kwargs["metadata_"] = kwargs.pop("metadata")
    hypothesis = Hypothesis(**kwargs)
    db.add(hypothesis)
    await db.flush()
    await db.refresh(hypothesis)
    return hypothesis


async def get_hypothesis(
    db: AsyncSession, hypothesis_id: uuid.UUID, *, tenant_id: Optional[uuid.UUID] = None,
) -> Optional[Hypothesis]:
    query = select(Hypothesis).where(Hypothesis.id == hypothesis_id)
    if tenant_id is not None:
        query = query.where(Hypothesis.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def list_hypotheses(
    db: AsyncSession,
    *,
    tenant_id: Optional[uuid.UUID] = None,
    status: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    created_by: Optional[str] = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    search: Optional[str] = None,
    is_archived: bool = False,
    parent_id: Optional[uuid.UUID] = None,
    channel: Optional[str] = None,
    deadline_before: Optional[datetime] = None,
    deadline_after: Optional[datetime] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Hypothesis], int]:
    query = select(Hypothesis)
    count_query = select(func.count(Hypothesis.id))

    filters = [Hypothesis.is_archived == is_archived]
    if tenant_id is not None:
        filters.append(Hypothesis.tenant_id == tenant_id)

    if status:
        filters.append(Hypothesis.status.in_(status))
    if tags:
        for tag in tags:
            filters.append(Hypothesis.tags.any(tag))
    if created_by:
        filters.append(Hypothesis.created_by == created_by)
    if confidence_min is not None:
        filters.append(Hypothesis.confidence >= confidence_min)
    if confidence_max is not None:
        filters.append(Hypothesis.confidence <= confidence_max)
    if search:
        # Escape LIKE wildcards to prevent pattern injection
        safe = search.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        search_filter = or_(
            Hypothesis.statement.ilike(f"%{safe}%"),
            Hypothesis.context.ilike(f"%{safe}%"),
            Hypothesis.falsification_criteria.ilike(f"%{safe}%"),
            Hypothesis.null_hypothesis.ilike(f"%{safe}%"),
        )
        filters.append(search_filter)
    if parent_id is not None:
        filters.append(Hypothesis.parent_id == parent_id)
    if channel:
        filters.append(Hypothesis.channel == channel)
    if deadline_before is not None:
        filters.append(Hypothesis.deadline <= deadline_before)
    if deadline_after is not None:
        filters.append(Hypothesis.deadline >= deadline_after)

    where_clause = and_(*filters)
    query = query.where(where_clause)
    count_query = count_query.where(where_clause)

    _SORTABLE = {"created_at", "updated_at", "confidence", "deadline"}
    if sort_by not in _SORTABLE:
        sort_by = "created_at"
    sort_column = getattr(Hypothesis, sort_by)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    query = query.offset(offset).limit(min(limit, 200))

    result = await db.execute(query)
    hypotheses = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return hypotheses, total


_UPDATABLE_FIELDS = frozenset({
    "statement", "context", "falsification_criteria", "status", "confidence",
    "tags", "is_archived", "deadline", "metadata_", "null_hypothesis",
    "experimental_design", "significance_level", "outcome", "channel",
})


async def update_hypothesis(db: AsyncSession, hypothesis: Hypothesis, **kwargs) -> Hypothesis:
    # Map schema field 'metadata' to model attribute 'metadata_'
    if "metadata" in kwargs:
        kwargs["metadata_"] = kwargs.pop("metadata")
    for key, value in kwargs.items():
        if key not in _UPDATABLE_FIELDS:
            raise ValueError(f"Cannot update field: {key}")
        if value is not None:
            setattr(hypothesis, key, value)
    await db.flush()
    await db.refresh(hypothesis)
    return hypothesis


async def get_evidence_counts(db: AsyncSession, hypothesis_id: uuid.UUID) -> dict[str, int]:
    result = await db.execute(
        select(
            Evidence.evidence_type,
            func.count(Evidence.id),
        )
        .where(Evidence.hypothesis_id == hypothesis_id)
        .group_by(Evidence.evidence_type)
    )
    counts = {"supporting": 0, "contradicting": 0, "neutral": 0}
    for evidence_type, count in result.all():
        counts[evidence_type] = count
    return counts


async def get_evidence_counts_batch(
    db: AsyncSession, hypothesis_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict[str, int]]:
    """Fetch evidence counts for multiple hypotheses in a single query (avoids N+1)."""
    if not hypothesis_ids:
        return {}
    result = await db.execute(
        select(
            Evidence.hypothesis_id,
            Evidence.evidence_type,
            func.count(Evidence.id),
        )
        .where(Evidence.hypothesis_id.in_(hypothesis_ids))
        .group_by(Evidence.hypothesis_id, Evidence.evidence_type)
    )
    counts: dict[uuid.UUID, dict[str, int]] = {
        hid: {"supporting": 0, "contradicting": 0, "neutral": 0}
        for hid in hypothesis_ids
    }
    for hypothesis_id, evidence_type, count in result.all():
        counts[hypothesis_id][evidence_type] = count
    return counts


async def get_lineage(
    db: AsyncSession, hypothesis_id: uuid.UUID, *, tenant_id: Optional[uuid.UUID] = None,
) -> list[Hypothesis]:
    """Fetch the full revision chain using recursive CTEs (2 queries instead of N)."""
    current = await get_hypothesis(db, hypothesis_id, tenant_id=tenant_id)
    if not current:
        return []

    # Walk up to root using WITH RECURSIVE
    ancestors_cte = (
        select(Hypothesis.id, Hypothesis.parent_id, literal_column("0").label("depth"))
        .where(Hypothesis.id == hypothesis_id)
    )
    if tenant_id is not None:
        ancestors_cte = ancestors_cte.where(Hypothesis.tenant_id == tenant_id)
    ancestors_cte = ancestors_cte.cte(name="ancestors", recursive=True)

    parent_join = (
        select(Hypothesis.id, Hypothesis.parent_id, (ancestors_cte.c.depth + 1).label("depth"))
        .join(ancestors_cte, Hypothesis.id == ancestors_cte.c.parent_id)
    )
    if tenant_id is not None:
        parent_join = parent_join.where(Hypothesis.tenant_id == tenant_id)
    ancestors_cte = ancestors_cte.union_all(parent_join)

    ancestor_ids_query = select(ancestors_cte.c.id, ancestors_cte.c.depth)
    ancestor_result = await db.execute(ancestor_ids_query)
    ancestor_rows = ancestor_result.all()
    ancestor_ids = {row.id for row in ancestor_rows}

    # Walk down to descendants using WITH RECURSIVE
    descendants_cte = (
        select(Hypothesis.id, Hypothesis.parent_id, literal_column("0").label("depth"))
        .where(Hypothesis.id == hypothesis_id)
    )
    if tenant_id is not None:
        descendants_cte = descendants_cte.where(Hypothesis.tenant_id == tenant_id)
    descendants_cte = descendants_cte.cte(name="descendants", recursive=True)

    child_join = (
        select(Hypothesis.id, Hypothesis.parent_id, (descendants_cte.c.depth + 1).label("depth"))
        .join(descendants_cte, Hypothesis.parent_id == descendants_cte.c.id)
    )
    if tenant_id is not None:
        child_join = child_join.where(Hypothesis.tenant_id == tenant_id)
    descendants_cte = descendants_cte.union_all(child_join)

    descendant_ids_query = select(descendants_cte.c.id)
    descendant_result = await db.execute(descendant_ids_query)
    descendant_ids = {row.id for row in descendant_result.all()}

    # Fetch all hypotheses in a single query
    all_ids = list(ancestor_ids | descendant_ids)
    if not all_ids:
        return [current]

    query = select(Hypothesis).where(Hypothesis.id.in_(all_ids))
    if tenant_id is not None:
        query = query.where(Hypothesis.tenant_id == tenant_id)
    query = query.order_by(Hypothesis.created_at.asc())

    result = await db.execute(query)
    return list(result.scalars().all())
