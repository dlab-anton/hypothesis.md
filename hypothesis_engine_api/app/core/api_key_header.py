from fastapi import HTTPException
from fastapi.security import APIKeyHeader as FastAPIKeyHeader


class APIKeyHeader(FastAPIKeyHeader):
    """Preserve the API's missing-key 403 response across FastAPI upgrades."""

    def make_not_authenticated_error(self) -> HTTPException:
        return HTTPException(status_code=403, detail="Not authenticated")
