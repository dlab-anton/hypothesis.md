import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....api.deps import get_db_session
from ....core.auth_context import AuthContext
from ....core.security import get_api_key
from ....core.constants import EvidenceType
from ....core.exceptions import NotFoundError
from ....crud import crud_hypothesis, crud_evidence
from ....schemas.evidence import EvidenceCreate, EvidenceRead, EvidenceCreateResponse
from ....schemas.common import PaginatedResponse
from ....services import event_service
from ....services import evidence_import_service
from ....services import idempotency_service
from ....services.idempotency_service import IdempotencyKey
from . import build_hypothesis_read

router = APIRouter(prefix="/hypotheses/{hypothesis_id}/evidence", tags=["evidence"])


@router.post(
    "",
    response_model=EvidenceCreateResponse,
    status_code=201,
    summary="Add evidence",
    responses={409: {"description": "Target channel mismatch or conflicting keyed request"}},
)
async def add_evidence(
    hypothesis_id: uuid.UUID,
    data: EvidenceCreate,
    idempotency_key: IdempotencyKey = None,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    """Add evidence to a hypothesis. Optionally update confidence in the same call.
    Returns both the new evidence and the updated hypothesis. Evidence is immutable once created.
    Each entry records `confidence_after` — the hypothesis confidence at this point in time."""
    # Keyed delivery requires an actual authenticated tenant. Preserve legacy
    # unkeyed master behavior without treating declared attribution as scope.
    evidence_payload = data.model_dump(mode="json")
    if "expected_channel_id" not in data.model_fields_set:
        # Preserve the precondition-free digest used by existing keyed clients.
        evidence_payload.pop("expected_channel_id")
    delivery_id, replay = await idempotency_service.reserve(
        db, auth.require_tenant() if idempotency_key is not None else auth.tenant_id,
        "evidence:create", idempotency_key,
        {"hypothesis_id": str(hypothesis_id), "evidence": evidence_payload},
    )
    if replay is not None:
        return replay

    hypothesis = await evidence_import_service.lock_evidence_target(
        db,
        hypothesis_id,
        tenant_id=auth.tenant_id,
        expected_channel_id=data.expected_channel_id,
    )

    if hypothesis.is_archived:
        raise HTTPException(
            status_code=409,
            detail="Cannot add evidence to an archived hypothesis. Unarchive it first.",
        )

    evidence = await crud_evidence.create_evidence(
        db,
        hypothesis_id=hypothesis_id,
        content=data.content,
        source=data.source,
        evidence_type=data.evidence_type,
        strength=data.strength,
        created_by=data.created_by,
    )

    await event_service.emit_evidence_added(
        db, hypothesis_id, evidence.id, data.evidence_type, data.created_by
    )

    # Optionally update confidence
    if data.confidence is not None and data.confidence != hypothesis.confidence:
        # Warn if contradicting evidence is raising confidence (possible confirmation bias)
        if (
            data.evidence_type == "contradicting"
            and hypothesis.confidence is not None
            and data.confidence > hypothesis.confidence
        ):
            await event_service.emit_confidence_contradiction_warning(
                db, hypothesis_id, hypothesis.confidence, data.confidence,
                str(evidence.id), data.created_by,
            )

        await event_service.emit_confidence_changed(
            db, hypothesis_id, hypothesis.confidence, data.confidence, data.created_by
        )
        hypothesis = await crud_hypothesis.update_hypothesis(db, hypothesis, confidence=data.confidence)

    # Snapshot the hypothesis confidence at this point in time
    evidence.confidence_after = hypothesis.confidence

    # Propagate events to related hypotheses
    await event_service.propagate_evidence_events(
        db, hypothesis_id, evidence.id, data.evidence_type, data.created_by,
        tenant_id=auth.tenant_id,
    )

    await db.flush()
    counts = await crud_hypothesis.get_evidence_counts(db, hypothesis_id)

    body = await idempotency_service.complete(db, delivery_id, EvidenceCreateResponse(
        evidence=EvidenceRead.model_validate(evidence),
        hypothesis=build_hypothesis_read(hypothesis, counts),
    ))
    await db.commit()
    return body


@router.get("", response_model=PaginatedResponse[EvidenceRead], summary="List evidence")
async def list_evidence(
    hypothesis_id: uuid.UUID,
    evidence_type: Optional[EvidenceType] = Query(None, description="Filter by evidence type"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    hypothesis = await crud_hypothesis.get_hypothesis(db, hypothesis_id, tenant_id=auth.tenant_id)
    if not hypothesis:
        raise NotFoundError(f"Hypothesis {hypothesis_id} not found")

    evidence_list, total = await crud_evidence.list_evidence(
        db, hypothesis_id, evidence_type=evidence_type, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[EvidenceRead.model_validate(e) for e in evidence_list],
        total=total,
        offset=offset,
        limit=limit,
    )
