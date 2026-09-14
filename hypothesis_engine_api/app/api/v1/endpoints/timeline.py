import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....api.deps import get_db_session
from ....core.auth_context import AuthContext
from ....core.security import get_api_key
from ....core.constants import HypothesisStatus, VALID_TRANSITIONS
from ....core.exceptions import NotFoundError, InvalidTransitionError
from ....crud import crud_hypothesis, crud_event
from ....schemas.event import EventRead
from ....schemas.hypothesis import HypothesisRead, HypothesisRevise, LineageResponse
from ....services import event_service
from . import build_hypothesis_read as _build_read

router = APIRouter(prefix="/hypotheses/{hypothesis_id}", tags=["timeline"])


@router.get("/timeline", response_model=list[EventRead], summary="Get audit trail")
async def get_timeline(
    hypothesis_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session),
    auth: "AuthContext" = Depends(get_api_key),
):
    hypothesis = await crud_hypothesis.get_hypothesis(db, hypothesis_id, tenant_id=auth.tenant_id)
    if not hypothesis:
        raise NotFoundError(f"Hypothesis {hypothesis_id} not found")

    events = await crud_event.list_events(db, hypothesis_id, offset=offset, limit=limit)
    return [EventRead.model_validate(e) for e in events]


@router.get("/lineage", response_model=LineageResponse, summary="Get revision chain")
async def get_lineage(
    hypothesis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    auth: "AuthContext" = Depends(get_api_key),
):
    hypothesis = await crud_hypothesis.get_hypothesis(db, hypothesis_id, tenant_id=auth.tenant_id)
    if not hypothesis:
        raise NotFoundError(f"Hypothesis {hypothesis_id} not found")

    chain = await crud_hypothesis.get_lineage(db, hypothesis_id, tenant_id=auth.tenant_id)
    counts_map = await crud_hypothesis.get_evidence_counts_batch(
        db, [h.id for h in chain]
    )
    items = [_build_read(h, counts_map[h.id]) for h in chain]

    return {"chain": items, "current_id": str(hypothesis_id)}


@router.post("/revise", response_model=HypothesisRead, status_code=201, summary="Revise hypothesis")
async def revise_hypothesis(
    hypothesis_id: uuid.UUID,
    data: HypothesisRevise,
    db: AsyncSession = Depends(get_db_session),
    auth: "AuthContext" = Depends(get_api_key),
):
    tenant_id = auth.require_tenant()
    hypothesis = await crud_hypothesis.get_hypothesis(db, hypothesis_id, tenant_id=tenant_id)
    if not hypothesis:
        raise NotFoundError(f"Hypothesis {hypothesis_id} not found")

    current_status = HypothesisStatus(hypothesis.status)
    if HypothesisStatus.REVISED not in VALID_TRANSITIONS.get(current_status, []):
        raise InvalidTransitionError(
            f"Cannot revise a hypothesis with status '{current_status}'"
        )

    # Create new hypothesis linked to parent
    new_hypothesis = await crud_hypothesis.create_hypothesis(
        db,
        statement=data.statement,
        context=data.context,
        falsification_criteria=data.falsification_criteria,
        status=HypothesisStatus.ACTIVE,
        confidence=data.confidence,
        initial_confidence=data.confidence,
        tags=data.tags,
        created_by=data.created_by,
        parent_id=hypothesis_id,
        deadline=data.deadline,
        metadata=data.metadata,
        null_hypothesis=data.null_hypothesis,
        experimental_design=data.experimental_design,
        significance_level=data.significance_level,
        channel=data.channel or hypothesis.channel,
        tenant_id=tenant_id,
    )

    # Mark old hypothesis as revised (include rationale in event data)
    await event_service.emit_revised(db, hypothesis.id, new_hypothesis.id, data.created_by, data.rationale)
    await event_service.emit_status_changed(db, hypothesis.id, hypothesis.status, HypothesisStatus.REVISED, data.created_by)
    await crud_hypothesis.update_hypothesis(db, hypothesis, status=HypothesisStatus.REVISED)

    # Emit created event for new hypothesis
    await event_service.emit_created(db, new_hypothesis.id, data.created_by)

    await db.commit()
    counts = await crud_hypothesis.get_evidence_counts(db, new_hypothesis.id)
    return _build_read(new_hypothesis, counts)
