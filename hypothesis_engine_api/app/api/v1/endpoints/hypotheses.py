import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.constants import HypothesisStatus, VALID_TRANSITIONS
from ....core.exceptions import NotFoundError, InvalidTransitionError
from ....api.deps import get_db_session
from ....core.rate_limit import limiter
from ....core.auth_context import AuthContext
from ....core.security import get_api_key
from ....crud import crud_hypothesis
from ....schemas.hypothesis import HypothesisCreate, HypothesisUpdate, HypothesisRead
from ....schemas.common import PaginatedResponse, StatsResponse, ACTOR_FILTER_PATTERN
from ....schemas.metrics import MetricsResponse
from ....services import event_service
from ....services import idempotency_service
from ....services.idempotency_service import IdempotencyKey
from ....services.stats_service import get_stats
from ....services.metrics_service import get_metrics
from . import build_hypothesis_read as _build_read

router = APIRouter(prefix="/hypotheses", tags=["hypotheses"])


@router.get("/stats", response_model=StatsResponse, summary="Dashboard statistics")
@limiter.limit("30/minute")
async def get_hypothesis_stats(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    """Aggregate stats: total hypotheses, counts by status, average confidence, top tags, and recent activity."""
    return await get_stats(db, tenant_id=auth.tenant_id)


@router.get("/metrics", response_model=MetricsResponse, summary="Prediction quality metrics")
@limiter.limit("15/minute")
async def get_hypothesis_metrics(
    request: Request,
    channel: Optional[str] = Query(None, description="Filter by channel"),
    created_by: Optional[str] = Query(None, max_length=255, description="Filter by agent"),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    """Compute 6 prediction quality metrics: Brier score, calibration, prediction value,
    falsification rigor, confidence dynamics, and learning rate."""
    return await get_metrics(
        db, tenant_id=auth.tenant_id, channel=channel, created_by=created_by
    )


@router.post("", response_model=HypothesisRead, status_code=201, summary="Create hypothesis")
async def create_hypothesis(
    data: HypothesisCreate,
    idempotency_key: IdempotencyKey = None,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    """Create a new hypothesis. Starts as `draft` (or `active` if specified). Set `falsification_criteria` to make it testable."""
    tenant_id = auth.require_tenant()
    # initial_confidence is immutable: use explicit value if provided, otherwise copy from confidence
    initial_confidence = data.initial_confidence if data.initial_confidence is not None else data.confidence
    payload = data.model_dump(mode="json")
    payload["initial_confidence"] = initial_confidence
    delivery_id, replay = await idempotency_service.reserve(
        db, tenant_id, "hypotheses:create", idempotency_key, payload,
    )
    if replay is not None:
        return replay
    hypothesis = await crud_hypothesis.create_hypothesis(
        db,
        statement=data.statement,
        context=data.context,
        falsification_criteria=data.falsification_criteria,
        status=data.status,
        confidence=data.confidence,
        initial_confidence=initial_confidence,
        tags=data.tags,
        created_by=data.created_by,
        deadline=data.deadline,
        metadata=data.metadata,
        null_hypothesis=data.null_hypothesis,
        experimental_design=data.experimental_design,
        significance_level=data.significance_level,
        outcome=data.outcome,
        channel=data.channel,
        tenant_id=tenant_id,
    )
    await event_service.emit_created(db, hypothesis.id, data.created_by)
    await db.flush()
    counts = await crud_hypothesis.get_evidence_counts(db, hypothesis.id)
    body = await idempotency_service.complete(db, delivery_id, _build_read(hypothesis, counts))
    await db.commit()
    return body


@router.get("", response_model=PaginatedResponse[HypothesisRead], summary="List hypotheses")
async def list_hypotheses(
    status: Optional[str] = Query(None, description="Comma-separated statuses"),
    tags: Optional[str] = Query(None, max_length=2000, description="Comma-separated tags (AND logic)"),
    created_by: Optional[str] = Query(None, max_length=255, pattern=ACTOR_FILTER_PATTERN),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    confidence_max: Optional[float] = Query(None, ge=0.0, le=1.0),
    search: Optional[str] = Query(None, max_length=500),
    channel: Optional[str] = Query(None, max_length=255, description="Filter by channel"),
    is_archived: bool = False,
    deadline_before: Optional[datetime] = Query(None, description="Hypotheses with deadline on or before this datetime"),
    deadline_after: Optional[datetime] = Query(None, description="Hypotheses with deadline on or after this datetime"),
    sort_by: str = Query("created_at", pattern="^(created_at|updated_at|confidence|deadline)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    status_list = [s.strip() for s in status.split(",")] if status else None
    if status_list:
        valid_statuses = {s.value for s in HypothesisStatus}
        invalid = [s for s in status_list if s not in valid_statuses]
        if invalid:
            raise HTTPException(status_code=422, detail=f"Invalid status values: {invalid}")
    tags_list = [t.strip() for t in tags.split(",")] if tags else None

    hypotheses, total = await crud_hypothesis.list_hypotheses(
        db,
        tenant_id=auth.tenant_id,
        status=status_list,
        tags=tags_list,
        created_by=created_by,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        search=search,
        channel=channel,
        is_archived=is_archived,
        deadline_before=deadline_before,
        deadline_after=deadline_after,
        sort_by=sort_by,
        sort_order=sort_order,
        offset=offset,
        limit=limit,
    )

    counts_map = await crud_hypothesis.get_evidence_counts_batch(
        db, [h.id for h in hypotheses]
    )
    items = [_build_read(h, counts_map[h.id]) for h in hypotheses]

    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{hypothesis_id}", response_model=HypothesisRead, summary="Get hypothesis")
async def get_hypothesis(
    hypothesis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    hypothesis = await crud_hypothesis.get_hypothesis(db, hypothesis_id, tenant_id=auth.tenant_id)
    if not hypothesis:
        raise NotFoundError(f"Hypothesis {hypothesis_id} not found")
    counts = await crud_hypothesis.get_evidence_counts(db, hypothesis.id)
    return _build_read(hypothesis, counts)


@router.patch("/{hypothesis_id}", response_model=HypothesisRead, summary="Update hypothesis")
async def update_hypothesis(
    hypothesis_id: uuid.UUID,
    data: HypothesisUpdate,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    hypothesis = await crud_hypothesis.get_hypothesis(db, hypothesis_id, tenant_id=auth.tenant_id)
    if not hypothesis:
        raise NotFoundError(f"Hypothesis {hypothesis_id} not found")

    # Block modifications on archived hypotheses (except unarchiving)
    if hypothesis.is_archived and data.is_archived is not False:
        raise HTTPException(
            status_code=409,
            detail="Cannot modify an archived hypothesis. Unarchive it first.",
        )

    event_actor = data.created_by or "system"

    # Validate status transition
    if data.status and data.status != hypothesis.status:
        current = HypothesisStatus(hypothesis.status)
        target = HypothesisStatus(data.status)
        if target not in VALID_TRANSITIONS.get(current, []):
            raise InvalidTransitionError(
                f"Cannot transition from '{current}' to '{target}'. "
                f"Valid transitions: {[str(s) for s in VALID_TRANSITIONS.get(current, [])]}"
            )

        # Require outcome when concluding a hypothesis
        _CONCLUSION_STATUSES = {HypothesisStatus.SUPPORTED, HypothesisStatus.REFUTED, HypothesisStatus.INCONCLUSIVE}
        if target in _CONCLUSION_STATUSES:
            has_outcome = data.outcome or hypothesis.outcome
            if not has_outcome:
                raise HTTPException(
                    status_code=422,
                    detail="Concluding a hypothesis requires an 'outcome' explaining the result. "
                    "Include an 'outcome' object in this request (e.g. {\"result\": \"...\", \"narrative\": \"...\"}).",
                )
        await event_service.emit_status_changed(db, hypothesis.id, hypothesis.status, data.status, event_actor)
        await event_service.propagate_status_events(
            db, hypothesis.id, hypothesis.status, data.status, event_actor,
            tenant_id=auth.tenant_id,
        )

    # Track confidence change
    if data.confidence is not None and data.confidence != hypothesis.confidence:
        await event_service.emit_confidence_changed(db, hypothesis.id, hypothesis.confidence, data.confidence, event_actor)

    # Handle archive/unarchive
    if data.is_archived is True and not hypothesis.is_archived:
        await event_service.emit_archived(db, hypothesis.id, event_actor)
    elif data.is_archived is False and hypothesis.is_archived:
        await event_service.emit_unarchived(db, hypothesis.id, event_actor)

    update_fields = data.model_dump(exclude_unset=True, exclude={"created_by"})
    hypothesis = await crud_hypothesis.update_hypothesis(db, hypothesis, **update_fields)
    await db.commit()
    counts = await crud_hypothesis.get_evidence_counts(db, hypothesis.id)
    return _build_read(hypothesis, counts)


@router.delete("/{hypothesis_id}", response_model=HypothesisRead, summary="Archive hypothesis")
async def archive_hypothesis(
    hypothesis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    hypothesis = await crud_hypothesis.get_hypothesis(db, hypothesis_id, tenant_id=auth.tenant_id)
    if not hypothesis:
        raise NotFoundError(f"Hypothesis {hypothesis_id} not found")

    if not hypothesis.is_archived:
        await event_service.emit_archived(db, hypothesis.id, "system")
    hypothesis = await crud_hypothesis.update_hypothesis(
        db, hypothesis, is_archived=True, status=HypothesisStatus.ARCHIVED.value
    )
    await db.commit()
    counts = await crud_hypothesis.get_evidence_counts(db, hypothesis.id)
    return _build_read(hypothesis, counts)
