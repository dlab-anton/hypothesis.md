import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ....api.deps import get_db_session
from ....core.auth_context import AuthContext
from ....core.security import get_api_key
from ....core.constants import EventType
from ....core.exceptions import NotFoundError
from ....core.rate_limit import limiter
from ....crud import crud_hypothesis, crud_relationship
from ....schemas.relationship import (
    RelationshipCreate,
    RelationshipRead,
    NetworkNode,
    NetworkEdge,
    NetworkResponse,
)
from ....services import event_service

router = APIRouter(tags=["relationships"])


@router.post(
    "/hypotheses/{hypothesis_id}/relationships",
    response_model=RelationshipRead,
    status_code=201,
    summary="Create relationship",
)
async def create_relationship(
    hypothesis_id: uuid.UUID,
    data: RelationshipCreate,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    tenant_id = auth.require_tenant()

    # Validate source hypothesis exists
    source = await crud_hypothesis.get_hypothesis(db, hypothesis_id, tenant_id=tenant_id)
    if not source:
        raise NotFoundError(f"Hypothesis {hypothesis_id} not found")

    # No self-referencing
    if data.target_hypothesis_id == hypothesis_id:
        raise HTTPException(status_code=400, detail="Cannot create a relationship to itself")

    # Validate target hypothesis exists
    target = await crud_hypothesis.get_hypothesis(db, data.target_hypothesis_id, tenant_id=tenant_id)
    if not target:
        raise NotFoundError(f"Hypothesis {data.target_hypothesis_id} not found")

    # Check for duplicates
    if await crud_relationship.check_duplicate(
        db, hypothesis_id, data.target_hypothesis_id, data.relationship_type,
        tenant_id=tenant_id,
    ):
        raise HTTPException(status_code=409, detail="This relationship already exists")

    rel = await crud_relationship.create_relationship(
        db,
        source_hypothesis_id=hypothesis_id,
        target_hypothesis_id=data.target_hypothesis_id,
        relationship_type=data.relationship_type,
        created_by=data.created_by,
        metadata=data.metadata,
        tenant_id=tenant_id,
    )

    # Emit events on both hypotheses
    rel_data = {
        "relationship_id": str(rel.id),
        "related_hypothesis_id": str(data.target_hypothesis_id),
        "relationship_type": data.relationship_type,
    }
    await event_service.emit_event(
        db, hypothesis_id, EventType.RELATIONSHIP_CREATED, data.created_by, rel_data,
    )
    await event_service.emit_event(
        db, data.target_hypothesis_id, EventType.RELATIONSHIP_CREATED, data.created_by,
        {**rel_data, "related_hypothesis_id": str(hypothesis_id)},
    )

    await db.commit()
    return RelationshipRead.from_model(rel)


@router.get(
    "/hypotheses/{hypothesis_id}/relationships",
    response_model=list[RelationshipRead],
    summary="List relationships",
)
async def list_relationships(
    hypothesis_id: uuid.UUID,
    relationship_type: str | None = Query(None, max_length=50, pattern=r'^(decomposes_into|competes_with|depends_on)$', description="Filter by relationship type"),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    hypothesis = await crud_hypothesis.get_hypothesis(db, hypothesis_id, tenant_id=auth.tenant_id)
    if not hypothesis:
        raise NotFoundError(f"Hypothesis {hypothesis_id} not found")

    rels = await crud_relationship.list_relationships(
        db, hypothesis_id, relationship_type=relationship_type,
        tenant_id=auth.tenant_id,
    )
    return [RelationshipRead.from_model(r) for r in rels]


@router.delete(
    "/hypotheses/{hypothesis_id}/relationships/{relationship_id}",
    status_code=204,
    summary="Remove relationship",
)
async def delete_relationship(
    hypothesis_id: uuid.UUID,
    relationship_id: uuid.UUID,
    created_by: str = Query("system", max_length=255, pattern=r'^[\w\-\.@\s]+$', description="Who is removing this relationship"),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    rel = await crud_relationship.get_relationship(db, relationship_id, tenant_id=auth.tenant_id)
    if not rel:
        raise NotFoundError(f"Relationship {relationship_id} not found")

    # Verify the relationship belongs to this hypothesis
    if rel.source_hypothesis_id != hypothesis_id and rel.target_hypothesis_id != hypothesis_id:
        raise NotFoundError(f"Relationship {relationship_id} not found for hypothesis {hypothesis_id}")

    # Emit removal events on both hypotheses
    for h_id, other_id in [
        (rel.source_hypothesis_id, rel.target_hypothesis_id),
        (rel.target_hypothesis_id, rel.source_hypothesis_id),
    ]:
        await event_service.emit_event(
            db, h_id, EventType.RELATIONSHIP_REMOVED, created_by,
            {
                "relationship_id": str(rel.id),
                "related_hypothesis_id": str(other_id),
                "relationship_type": rel.relationship_type,
            },
        )

    await crud_relationship.delete_relationship(db, rel)
    await db.commit()


@router.get(
    "/hypotheses/{hypothesis_id}/network",
    response_model=NetworkResponse,
    summary="Get relationship graph",
)
@limiter.limit("15/minute")
async def get_network(
    request: Request,
    hypothesis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    hypothesis = await crud_hypothesis.get_hypothesis(db, hypothesis_id, tenant_id=auth.tenant_id)
    if not hypothesis:
        raise NotFoundError(f"Hypothesis {hypothesis_id} not found")

    hypotheses, relationships = await crud_relationship.get_network(db, hypothesis_id, tenant_id=auth.tenant_id)

    nodes = [
        NetworkNode(
            id=h.id,
            statement=h.statement,
            status=h.status,
            confidence=h.confidence,
            created_by=h.created_by,
        )
        for h in hypotheses
    ]
    edges = [
        NetworkEdge(
            id=r.id,
            source_id=r.source_hypothesis_id,
            target_id=r.target_hypothesis_id,
            relationship_type=r.relationship_type,
            created_by=r.created_by,
        )
        for r in relationships
    ]

    return NetworkResponse(root_id=hypothesis_id, nodes=nodes, edges=edges)
