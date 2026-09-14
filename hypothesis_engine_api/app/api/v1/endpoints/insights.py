import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....api.deps import get_db_session
from ....core.auth_context import AuthContext
from ....core.security import get_api_key
from ....core.constants import InsightType
from ....core.exceptions import NotFoundError
from ....crud import crud_insight
from ....schemas.insight import InsightCreate, InsightUpdate, InsightRead
from ....schemas.common import PaginatedResponse, ACTOR_FILTER_PATTERN
from ....services import idempotency_service
from ....services.idempotency_service import IdempotencyKey

router = APIRouter(tags=["insights"])


@router.post(
    "/insights",
    response_model=InsightRead,
    status_code=201,
    summary="Create insight",
)
async def create_insight(
    data: InsightCreate,
    idempotency_key: IdempotencyKey = None,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    tenant_id = auth.require_tenant()
    delivery_id, replay = await idempotency_service.reserve(
        db, tenant_id, "insights:create", idempotency_key, data.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    insight = await crud_insight.create_insight(
        db,
        channel=data.channel,
        insight_type=data.insight_type,
        content=data.content,
        created_by=data.created_by,
        metadata=data.metadata,
        tenant_id=tenant_id,
    )
    body = await idempotency_service.complete(db, delivery_id, InsightRead.from_model(insight))
    await db.commit()
    return body


@router.get(
    "/insights",
    response_model=PaginatedResponse[InsightRead],
    summary="List insights",
)
async def list_insights(
    channel: str | None = Query(None, max_length=255, description="Filter by channel"),
    type: InsightType | None = Query(None, alias="type", description="Filter by insight type"),
    created_by: str | None = Query(None, max_length=255, pattern=ACTOR_FILTER_PATTERN, description="Filter by agent"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    insights, total = await crud_insight.list_insights(
        db,
        channel=channel,
        insight_type=type,
        created_by=created_by,
        offset=offset,
        limit=limit,
        tenant_id=auth.tenant_id,
    )
    return PaginatedResponse(
        items=[InsightRead.from_model(i) for i in insights],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/insights/{insight_id}",
    response_model=InsightRead,
    summary="Get insight",
)
async def get_insight(
    insight_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    insight = await crud_insight.get_insight(db, insight_id, tenant_id=auth.tenant_id)
    if not insight:
        raise NotFoundError(f"Insight {insight_id} not found")
    return InsightRead.from_model(insight)


@router.patch(
    "/insights/{insight_id}",
    response_model=InsightRead,
    summary="Update insight",
)
async def update_insight(
    insight_id: uuid.UUID,
    data: InsightUpdate,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    insight = await crud_insight.get_insight(db, insight_id, tenant_id=auth.tenant_id)
    if not insight:
        raise NotFoundError(f"Insight {insight_id} not found")

    updated = await crud_insight.update_insight(
        db,
        insight,
        content=data.content,
        metadata=data.metadata,
        updated_by=data.updated_by,
    )
    await db.commit()
    return InsightRead.from_model(updated)


@router.delete(
    "/insights/{insight_id}",
    status_code=204,
    summary="Delete insight",
)
async def delete_insight(
    insight_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    insight = await crud_insight.get_insight(db, insight_id, tenant_id=auth.tenant_id)
    if not insight:
        raise NotFoundError(f"Insight {insight_id} not found")
    await crud_insight.delete_insight(db, insight)
    await db.commit()
