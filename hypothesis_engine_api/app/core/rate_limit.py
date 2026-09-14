from fastapi import Request
from slowapi import Limiter


def _get_rate_limit_key(request: Request) -> str:
    """Rate limit key: use API key prefix if present, otherwise client IP."""
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"key:{api_key[:16]}"
    return f"ip:{request.client.host}" if request.client else "ip:unknown"


limiter = Limiter(
    key_func=_get_rate_limit_key,
    default_limits=["120/minute"],
)
