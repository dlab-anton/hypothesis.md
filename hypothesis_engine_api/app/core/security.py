import secrets

from fastapi import Depends, Security, HTTPException, status
from .api_key_header import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from .auth_context import AuthContext
from .config import settings
from ..api.deps import get_db_session
from ..crud import crud_api_key

API_MASTER_KEY = settings.API_MASTER_KEY

api_key_header_auth = APIKeyHeader(name="X-API-Key", auto_error=True)


async def get_api_key(
    api_key_header: str = Security(api_key_header_auth),
    db: AsyncSession = Depends(get_db_session),
) -> AuthContext:
    """
    Validate the API key: accepts the master key or any active generated key.
    Uses constant-time comparison to prevent timing attacks.
    Returns an AuthContext with tenant information.
    """
    return await authenticate_api_key(api_key_header, db)


async def authenticate_api_key(
    api_key_header: str,
    db: AsyncSession,
    *,
    touch_last_used: bool = True,
    lock_generated_key_for_share: bool = False,
) -> AuthContext:
    """Authenticate a key using an existing session controlled by the caller."""
    # Constant-time comparison for master key (prevents timing side-channel)
    if secrets.compare_digest(api_key_header, API_MASTER_KEY):
        return AuthContext(tenant_id=None, is_master=True)

    # Check generated keys (hash lookup — already timing-safe since we compare hashes)
    api_key = await crud_api_key.validate_key(
        db,
        api_key_header,
        touch_last_used=touch_last_used,
        lock_for_share=lock_generated_key_for_share,
    )
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return AuthContext(tenant_id=api_key.tenant_id, is_master=False)
