import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Authenticated request context extracted from the API key."""
    tenant_id: Optional[uuid.UUID]
    is_master: bool

    def require_tenant(self) -> uuid.UUID:
        """Return tenant_id or raise if master key is used without a tenant scope.

        Master keys have tenant_id=None but most write operations require a
        tenant context (tenant_id is NOT NULL in the DB).
        """
        if self.tenant_id is None:
            from ..core.exceptions import HypothesisEngineError
            raise HypothesisEngineError(
                status_code=400,
                detail="Master key cannot create tenant-scoped resources directly. "
                       "Use a workspace API key instead.",
            )
        return self.tenant_id
