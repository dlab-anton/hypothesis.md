import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..crud.crud_event import create_event
from ..core.constants import EventType


async def emit_event(
    db: AsyncSession,
    hypothesis_id: uuid.UUID,
    event_type: EventType,
    created_by: str,
    data: dict[str, Any] | None = None,
) -> None:
    await create_event(
        db,
        hypothesis_id=hypothesis_id,
        event_type=event_type,
        data=data or {},
        created_by=created_by,
    )


async def emit_created(db: AsyncSession, hypothesis_id: uuid.UUID, created_by: str) -> None:
    await emit_event(db, hypothesis_id, EventType.CREATED, created_by)


async def emit_status_changed(
    db: AsyncSession, hypothesis_id: uuid.UUID, old_status: str, new_status: str, created_by: str
) -> None:
    await emit_event(
        db, hypothesis_id, EventType.STATUS_CHANGED, created_by,
        {"old_status": old_status, "new_status": new_status},
    )


async def emit_confidence_changed(
    db: AsyncSession, hypothesis_id: uuid.UUID, old_confidence: float | None, new_confidence: float, created_by: str
) -> None:
    await emit_event(
        db, hypothesis_id, EventType.CONFIDENCE_CHANGED, created_by,
        {"old_confidence": old_confidence, "new_confidence": new_confidence},
    )


async def emit_evidence_added(
    db: AsyncSession, hypothesis_id: uuid.UUID, evidence_id: uuid.UUID, evidence_type: str, created_by: str
) -> None:
    await emit_event(
        db, hypothesis_id, EventType.EVIDENCE_ADDED, created_by,
        {"evidence_id": str(evidence_id), "evidence_type": evidence_type},
    )


async def emit_revised(
    db: AsyncSession, hypothesis_id: uuid.UUID, new_hypothesis_id: uuid.UUID, created_by: str, rationale: str = ""
) -> None:
    await emit_event(
        db, hypothesis_id, EventType.REVISED, created_by,
        {"new_hypothesis_id": str(new_hypothesis_id), "rationale": rationale},
    )


async def emit_confidence_contradiction_warning(
    db: AsyncSession, hypothesis_id: uuid.UUID,
    old_confidence: float, new_confidence: float,
    evidence_id: str, created_by: str,
) -> None:
    """Warn when contradicting evidence is added but confidence increases."""
    await emit_event(
        db, hypothesis_id, EventType.CONFIDENCE_CONTRADICTION_WARNING, created_by,
        {
            "old_confidence": old_confidence,
            "new_confidence": new_confidence,
            "evidence_id": evidence_id,
            "warning": "Contradicting evidence was added but confidence increased. Review for confirmation bias.",
        },
    )


async def emit_archived(db: AsyncSession, hypothesis_id: uuid.UUID, created_by: str) -> None:
    await emit_event(db, hypothesis_id, EventType.ARCHIVED, created_by)


async def emit_unarchived(db: AsyncSession, hypothesis_id: uuid.UUID, created_by: str) -> None:
    await emit_event(db, hypothesis_id, EventType.UNARCHIVED, created_by)


# --- Relationship-aware event propagation ---

async def propagate_evidence_events(
    db: AsyncSession,
    hypothesis_id: uuid.UUID,
    evidence_id: uuid.UUID,
    evidence_type: str,
    actor: str,
    tenant_id: uuid.UUID | None = None,
) -> None:
    """Emit events on related hypotheses when evidence is added."""
    from ..crud.crud_relationship import list_relationships
    from ..core.constants import RelationshipType

    relationships = await list_relationships(db, hypothesis_id, tenant_id=tenant_id)
    for rel in relationships:
        data = {
            "source_hypothesis_id": str(hypothesis_id),
            "evidence_id": str(evidence_id),
            "evidence_type": evidence_type,
            "relationship_type": rel.relationship_type,
        }

        if rel.relationship_type == RelationshipType.DECOMPOSES_INTO:
            # This hypothesis is a child → notify the parent
            if rel.target_hypothesis_id == hypothesis_id:
                await emit_event(
                    db, rel.source_hypothesis_id,
                    EventType.CHILD_EVIDENCE_ADDED, actor, data,
                )
        elif rel.relationship_type == RelationshipType.COMPETES_WITH:
            # Symmetric → notify the other side
            other_id = (
                rel.target_hypothesis_id
                if rel.source_hypothesis_id == hypothesis_id
                else rel.source_hypothesis_id
            )
            await emit_event(
                db, other_id,
                EventType.COMPETING_EVIDENCE_ADDED, actor, data,
            )
        elif rel.relationship_type == RelationshipType.DEPENDS_ON:
            # If something I depend on gets evidence, I should know
            # source depends on target, so if target gets evidence → notify source
            if rel.target_hypothesis_id == hypothesis_id:
                await emit_event(
                    db, rel.source_hypothesis_id,
                    EventType.DEPENDENCY_EVIDENCE_ADDED, actor, data,
                )


async def propagate_status_events(
    db: AsyncSession,
    hypothesis_id: uuid.UUID,
    old_status: str,
    new_status: str,
    actor: str,
    tenant_id: uuid.UUID | None = None,
) -> None:
    """Emit events on related hypotheses when status changes."""
    from ..crud.crud_relationship import list_relationships
    from ..core.constants import RelationshipType

    relationships = await list_relationships(db, hypothesis_id, tenant_id=tenant_id)
    for rel in relationships:
        data = {
            "source_hypothesis_id": str(hypothesis_id),
            "old_status": old_status,
            "new_status": new_status,
            "relationship_type": rel.relationship_type,
        }

        if rel.relationship_type == RelationshipType.DECOMPOSES_INTO:
            if rel.target_hypothesis_id == hypothesis_id:
                await emit_event(
                    db, rel.source_hypothesis_id,
                    EventType.CHILD_STATUS_CHANGED, actor, data,
                )
        elif rel.relationship_type == RelationshipType.COMPETES_WITH:
            other_id = (
                rel.target_hypothesis_id
                if rel.source_hypothesis_id == hypothesis_id
                else rel.source_hypothesis_id
            )
            await emit_event(
                db, other_id,
                EventType.COMPETING_STATUS_CHANGED, actor, data,
            )
        elif rel.relationship_type == RelationshipType.DEPENDS_ON:
            # If something I depend on changes status, I should know
            if rel.target_hypothesis_id == hypothesis_id:
                await emit_event(
                    db, rel.source_hypothesis_id,
                    EventType.DEPENDENCY_STATUS_CHANGED, actor, data,
                )
