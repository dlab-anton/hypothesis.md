import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.api_key import ApiKey

KEY_PREFIX = "he_"


def generate_key() -> str:
    """Generate a random API key with he_ prefix."""
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(raw_key: str) -> str:
    """SHA-256 hash of an API key. Safe because keys have high entropy."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def extract_prefix(raw_key: str) -> str:
    """First 10 chars of the key for display/identification."""
    return raw_key[:10]


async def create_api_key(
    db: AsyncSession,
    *,
    label: Optional[str] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> tuple[ApiKey, str]:
    """Create a new API key.
    If tenant_id is provided, validates the tenant exists (at least one key for it).
    If tenant_id is None, generates a new tenant UUID.
    Returns (model, raw_key). The raw key is only available here.
    """
    if tenant_id is not None:
        result = await db.execute(
            select(ApiKey).where(ApiKey.tenant_id == tenant_id).limit(1)
        )
        if result.scalar_one_or_none() is None:
            raise ValueError(f"Tenant {tenant_id} not found")
    else:
        tenant_id = uuid.uuid4()

    raw_key = generate_key()
    api_key = ApiKey(
        key_hash=hash_key(raw_key),
        key_prefix=extract_prefix(raw_key),
        label=label,
        tenant_id=tenant_id,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)
    return api_key, raw_key


_LAST_USED_THROTTLE_SECONDS = 3600  # Only update last_used_at once per hour


async def validate_key(
    db: AsyncSession,
    raw_key: str,
    *,
    touch_last_used: bool = True,
    lock_for_share: bool = False,
) -> Optional[ApiKey]:
    """Look up a key by its hash. Returns the ApiKey if valid and active, else None."""
    key_hash = hash_key(raw_key)
    query = select(ApiKey).where(
        ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)
    )
    if lock_for_share:
        query = query.with_for_update(read=True)
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()
    if api_key and touch_last_used:
        now = datetime.now(timezone.utc)
        # Throttle last_used_at writes to reduce DB pressure.
        # Use flush (not commit) to preserve the unit-of-work pattern —
        # the endpoint handler will commit along with its own writes.
        if (
            api_key.last_used_at is None
            or (now - api_key.last_used_at).total_seconds() > _LAST_USED_THROTTLE_SECONDS
        ):
            api_key.last_used_at = now
            await db.flush()
    return api_key


async def list_api_keys(
    db: AsyncSession,
    *,
    tenant_id: Optional[uuid.UUID] = None,
    include_revoked: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> list[ApiKey]:
    """List API keys. If tenant_id is provided, scopes to that tenant only."""
    query = select(ApiKey)
    if tenant_id is not None:
        query = query.where(ApiKey.tenant_id == tenant_id)
    if not include_revoked:
        query = query.where(ApiKey.is_active.is_(True))
    query = query.order_by(ApiKey.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_api_key(db: AsyncSession, key_id: uuid.UUID) -> Optional[ApiKey]:
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    return result.scalar_one_or_none()


async def revoke_api_key(db: AsyncSession, api_key: ApiKey) -> ApiKey:
    """Soft-revoke a key by setting is_active=False."""
    api_key.is_active = False
    await db.flush()
    await db.refresh(api_key)
    return api_key
