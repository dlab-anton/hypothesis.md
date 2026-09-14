from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....api.deps import get_db_session
from ....core.auth_context import AuthContext
from ....core.security import get_api_key
from ....core.exceptions import NotFoundError, InvalidTransitionError
from ....crud import crud_channel
from ....schemas.channel import ChannelCreate, ChannelUpdate, ChannelRead
from ....schemas.common import PaginatedResponse, normalize_channel

router = APIRouter(tags=["channels"])


@router.post(
    "/channels",
    response_model=ChannelRead,
    status_code=201,
    summary="Create channel",
)
async def create_channel(
    data: ChannelCreate,
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    tenant_id = auth.require_tenant()
    existing = await crud_channel.get_channel_by_name(db, data.name, tenant_id=tenant_id)
    if existing:
        raise InvalidTransitionError(
            detail=f"Channel '{data.name}' already exists",
            status_code=409,
        )
    channel = await crud_channel.create_channel(
        db,
        name=data.name,
        goal=data.goal,
        created_by=data.created_by,
        metadata=data.metadata,
        tenant_id=tenant_id,
    )
    await db.commit()
    return ChannelRead.from_model(channel)


@router.get(
    "/channels",
    response_model=PaginatedResponse[ChannelRead],
    summary="List channels",
)
async def list_channels(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    channels, total = await crud_channel.list_channels(
        db, offset=offset, limit=limit, tenant_id=auth.tenant_id,
    )
    return PaginatedResponse(
        items=[ChannelRead.from_model(c) for c in channels],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/channels/{name}",
    response_model=ChannelRead,
    summary="Get channel by name",
)
async def get_channel(
    name: str = Path(..., min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    normalized = normalize_channel(name) or name
    channel = await crud_channel.get_channel_by_name(db, normalized, tenant_id=auth.tenant_id)
    if not channel:
        raise NotFoundError(f"Channel '{normalized}' not found")
    return ChannelRead.from_model(channel)


@router.patch(
    "/channels/{name}",
    response_model=ChannelRead,
    summary="Update channel",
)
async def update_channel(
    data: ChannelUpdate,
    name: str = Path(..., min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    normalized = normalize_channel(name) or name
    channel = await crud_channel.get_channel_by_name(db, normalized, tenant_id=auth.tenant_id)
    if not channel:
        raise NotFoundError(f"Channel '{normalized}' not found")

    updated = await crud_channel.update_channel(
        db,
        channel,
        goal=data.goal,
        metadata=data.metadata,
        updated_by=data.updated_by,
    )
    await db.commit()
    return ChannelRead.from_model(updated)


@router.delete(
    "/channels/{name}",
    status_code=204,
    summary="Delete channel",
)
async def delete_channel(
    name: str = Path(..., min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db_session),
    auth: AuthContext = Depends(get_api_key),
):
    normalized = normalize_channel(name) or name
    channel = await crud_channel.get_channel_by_name(db, normalized, tenant_id=auth.tenant_id)
    if not channel:
        raise NotFoundError(f"Channel '{normalized}' not found")
    await crud_channel.delete_channel(db, channel)
    await db.commit()
