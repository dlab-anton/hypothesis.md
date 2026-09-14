import asyncio
import secrets
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security, Query, status
from ....core.api_key_header import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from ....api.deps import get_db_session
from ....core.config import settings
from ....core.exceptions import NotFoundError
from ....core.security import authenticate_api_key
from ....crud import crud_api_key
from ....schemas.api_key import ApiKeyCreate, ApiKeyGenerated, ApiKeyInfo

router = APIRouter(tags=["keys"])

def _get_client_ip(request: Request) -> str:
    """Use the ASGI peer, normalized by the server's trusted-proxy settings."""
    return request.client.host if request.client else "unknown"


# --- In-memory rate limiter for key generation ---
_RATE_WINDOW = 3600  # 1 hour
_RATE_LIMIT = 5  # max keys per IP per window
_MAX_IPS = 10_000  # Prevent unbounded memory growth
_rate_log: dict[str, list[float]] = {}
_rate_lock = asyncio.Lock()


async def _check_rate_limit(client_ip: str) -> None:
    """Raise 429 if this IP has exceeded the key generation rate limit."""
    async with _rate_lock:
        now = time.monotonic()

        # Periodic cleanup: evict stale IPs when table gets large
        if len(_rate_log) >= _MAX_IPS:
            stale = [
                ip for ip, ts in _rate_log.items()
                if not ts or now - max(ts) >= _RATE_WINDOW
            ]
            for ip in stale:
                del _rate_log[ip]
            if client_ip not in _rate_log and len(_rate_log) >= _MAX_IPS:
                raise HTTPException(
                    status_code=429,
                    detail="Key issuance temporarily busy. Try again later.",
                    headers={"Retry-After": "60", "Cache-Control": "no-store"},
                )

        timestamps = _rate_log.get(client_ip, [])
        # Prune expired entries for this IP
        timestamps = [t for t in timestamps if now - t < _RATE_WINDOW]

        if len(timestamps) >= _RATE_LIMIT:
            oldest = min(timestamps)
            retry_after = int(_RATE_WINDOW - (now - oldest)) + 1
            _rate_log[client_ip] = timestamps
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(_RATE_LIMIT),
                    "X-RateLimit-Remaining": "0",
                    "Cache-Control": "no-store",
                },
            )

        timestamps.append(now)
        _rate_log[client_ip] = timestamps

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)
optional_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_master_key(key: str = Security(api_key_header)):
    """Only the master key can list/revoke keys."""
    if not secrets.compare_digest(key, settings.API_MASTER_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master key required for this operation",
        )
    return key


async def _resolve_caller(
    db: AsyncSession, raw_key: str,
) -> tuple[bool, uuid.UUID | None]:
    """Resolve an API key to (is_master, tenant_id). Raises 401 on invalid key."""
    if secrets.compare_digest(raw_key, settings.API_MASTER_KEY):
        return True, None
    caller = await crud_api_key.validate_key(db, raw_key)
    if caller is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return False, caller.tenant_id


@router.post(
    "/keys",
    response_model=ApiKeyGenerated,
    status_code=201,
    summary="Generate API key",
)
async def generate_key(
    request: Request,
    response: Response,
    data: ApiKeyCreate = ApiKeyCreate(),
    db: AsyncSession = Depends(get_db_session),
    api_key_value: str | None = Security(optional_api_key_header),
):
    """Generate a new API key.

    - No workspace_id: creates a new workspace (new UUID).
    - With workspace_id: an active key from that workspace or the master key is required.

    The full key is returned once — store it safely.
    Rate limited to 5 keys per IP per hour.
    """
    client_ip = _get_client_ip(request)
    await _check_rate_limit(client_ip)

    if data.tenant_id is not None:
        if api_key_value is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authenticated",
                headers={"Cache-Control": "no-store"},
            )
        try:
            caller = await authenticate_api_key(
                api_key_value,
                db,
                touch_last_used=False,
                lock_generated_key_for_share=True,
            )
        except HTTPException as error:
            error.headers = {**(error.headers or {}), "Cache-Control": "no-store"}
            raise
        if not caller.is_master and caller.tenant_id != data.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
                headers={"Cache-Control": "no-store"},
            )

    try:
        api_key, raw_key = await crud_api_key.create_api_key(
            db,
            label=data.label,
            tenant_id=data.tenant_id,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
            headers={"Cache-Control": "no-store"},
        )
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return ApiKeyGenerated(
        key=raw_key,
        prefix=api_key.key_prefix,
        label=api_key.label,
        tenant_id=api_key.tenant_id,
        created_at=api_key.created_at,
    )


@router.get(
    "/keys",
    response_model=list[ApiKeyInfo],
    summary="List API keys",
)
async def list_keys(
    include_revoked: bool = Query(False, description="Include revoked keys"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    api_key_value: str = Security(api_key_header),
):
    """List API keys. Master key sees all keys. Workspace members see their own workspace's keys."""
    is_master, caller_tenant = await _resolve_caller(db, api_key_value)
    keys = await crud_api_key.list_api_keys(
        db,
        tenant_id=None if is_master else caller_tenant,
        include_revoked=include_revoked,
        skip=skip,
        limit=limit,
    )
    return [ApiKeyInfo.from_model(k) for k in keys]


@router.delete(
    "/keys/{key_id}",
    status_code=204,
    summary="Revoke API key",
)
async def revoke_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: str = Depends(require_master_key),
):
    """Revoke an API key (admin only). Soft delete — sets is_active=False."""
    api_key = await crud_api_key.get_api_key(db, key_id)
    if not api_key:
        raise NotFoundError(f"API key {key_id} not found")
    await crud_api_key.revoke_api_key(db, api_key)
    await db.commit()
