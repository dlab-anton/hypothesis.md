import logging
import warnings

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from contextlib import asynccontextmanager
import sqlalchemy.exc
from slowapi.errors import RateLimitExceeded

from .core.config import settings
from .core.exceptions import HypothesisEngineError
from .core.rate_limit import limiter
from .api.v1.api import api_router

logger = logging.getLogger(__name__)

from .core.config import _PLACEHOLDER_MASTER_KEY, _KNOWN_WEAK_KEYS

API_DESCRIPTION = """\
Structured hypothesis tracking for AI agents. Form hypotheses, gather evidence,
track confidence over time, and let the system enforce scientific rigor.

---

## Getting Started

### 1. Create a workspace and API key

No authentication required. This creates an isolated workspace and returns your key:

```bash
curl -X POST https://hypothesis.md/api/v1/keys \\
  -H "Content-Type: application/json" \\
  -d '{"label": "my-agent"}'
```

Response:
```json
{"id": "uuid", "key": "he_abc123...", "tenant_id": "uuid", "label": "my-agent"}
```

> **Save the `key` immediately** — it's shown only once and cannot be retrieved later.

### 2. Authenticate

Data endpoints require an `X-API-Key` header. `/health`, `/SKILL.md`, and creating a new workspace through `POST /keys` are public. Issuing a key for an existing `tenant_id` requires an active key from that workspace or server master authority:

```bash
curl https://hypothesis.md/api/v1/hypotheses \\
  -H "X-API-Key: $HYPOTHESIS_API_KEY"
```

### 3. Create your first hypothesis

```bash
curl -X POST https://hypothesis.md/api/v1/hypotheses \\
  -H "X-API-Key: $HYPOTHESIS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "statement": "Response times degrade under concurrent load",
    "confidence": 0.6,
    "status": "active",
    "tags": ["performance"],
    "created_by": "my-agent"
  }'
```

### 4. Add evidence

```bash
curl -X POST https://hypothesis.md/api/v1/hypotheses/{id}/evidence \\
  -H "X-API-Key: $HYPOTHESIS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "content": "Load test showed p99 latency increased 3x at 100 concurrent users",
    "evidence_type": "supporting",
    "strength": 0.8,
    "created_by": "my-agent"
  }'
```

### 5. Update confidence and status

```bash
curl -X PATCH https://hypothesis.md/api/v1/hypotheses/{id} \\
  -H "X-API-Key: $HYPOTHESIS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"confidence": 0.85, "status": "testing", "created_by": "my-agent"}'
```

---

## Core Concepts

### Status Lifecycle

Hypotheses follow a strict lifecycle. No skipping steps — you must go through `testing` before reaching a conclusion.

```
draft → active → testing → supported | refuted | inconclusive → revised | archived
```

### Evidence Types

| Type | Purpose |
|------|---------|
| `supporting` | Confirms the hypothesis |
| `contradicting` | Challenges or disproves |
| `neutral` | Relevant context, neither for nor against |

Evidence is **immutable** — once created, it cannot be edited or deleted.
Each evidence entry records `confidence_after` showing where confidence stood after it was added.

### Relationships

Link hypotheses together to build structured reasoning:

| Type | Meaning |
|------|---------|
| `decomposes_into` | Parent → child breakdown |
| `competes_with` | Mutually exclusive alternatives (symmetric) |
| `depends_on` | Directed dependency |

### Workspaces & Multi-tenancy

All data is scoped by workspace. Each API key belongs to one workspace.

- `POST /keys` with no `tenant_id` → creates a **new** workspace
- `POST /keys` with `tenant_id` → issues a key only with an active same-workspace key or server master authority; the workspace ID alone grants no access
- Multiple agents can share a workspace — `created_by` records attribution, not authorization or verified human identity

### Insights

Channel-scoped domain knowledge that persists across hypothesis cycles:

| Type | Purpose |
|------|---------|
| `calibration` | Accuracy tracking |
| `bias` | Systematic errors to watch for |
| `prior` | Domain assumptions |
| `pattern` | Recurring observations |

---

## Agent Onboarding

For AI agents, the fastest way to learn the full API is to read the instruction file:

```bash
curl -sL https://hypothesis.md/SKILL.md
```

This returns a comprehensive guide covering every endpoint, schema, and workflow.
Additional reference docs: [REFERENCE.md](https://hypothesis.md/REFERENCE.md) |
[HEARTBEAT.md](https://hypothesis.md/HEARTBEAT.md)
"""

OPENAPI_TAGS = [
    {
        "name": "hypotheses",
        "description": "Create, list, update, and archive hypotheses. Supports full-text search, "
        "tag/status/channel filtering, confidence range queries, and deadline-based filtering.",
    },
    {
        "name": "evidence",
        "description": "Add and list evidence for a hypothesis. Evidence is **immutable** — once created, "
        "it cannot be edited or deleted. Each entry includes `confidence_after` showing the hypothesis "
        "confidence at the time the evidence was recorded.",
    },
    {
        "name": "timeline",
        "description": "Audit trail, revision lineage, and hypothesis revision. Every status change, "
        "confidence update, and evidence addition is recorded as an immutable event.",
    },
    {
        "name": "relationships",
        "description": "Link hypotheses together: `decomposes_into` (parent/child), `competes_with` "
        "(symmetric mutual exclusion), `depends_on` (directed dependency). "
        "Changes propagate signal events to related hypotheses.",
    },
    {
        "name": "agents",
        "description": "Agent coordination: list agents, view activity, check inbox for notifications, "
        "and get full status reports in markdown. Agents are identified by their `created_by` field.",
    },
    {
        "name": "insights",
        "description": "Channel-scoped domain knowledge that persists across hypothesis cycles. "
        "Types: `calibration` (accuracy tracking), `bias` (systematic errors), "
        "`prior` (domain assumptions), `pattern` (recurring observations).",
    },
    {
        "name": "keys",
        "description": "Self-service API key management. Generate keys to create or join workspaces. "
        "All data is tenant-scoped — each key carries a workspace ID.",
    },
    {
        "name": "health",
        "description": "Health checks, SKILL.md (agent instruction file), version info, and reference docs.",
    },
]


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    if settings.API_MASTER_KEY in _KNOWN_WEAK_KEYS:
        warnings.warn(
            "Using default master key — NOT SAFE FOR PRODUCTION. Set API_MASTER_KEY in .env.",
            stacklevel=1,
        )
    logger.info("%s v%s started (%s)", settings.PROJECT_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    yield
    logger.info("%s shutting down.", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=API_DESCRIPTION,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded. Try again later."},
        headers={"Retry-After": str(exc.detail)},
    )


@app.exception_handler(HypothesisEngineError)
async def hypothesis_engine_error_handler(request: Request, exc: HypothesisEngineError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(sqlalchemy.exc.IntegrityError)
async def integrity_error_handler(request: Request, exc: sqlalchemy.exc.IntegrityError):
    logger.warning("Database constraint violation (%s)", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Duplicate or constraint violation"},
    )


@app.exception_handler(sqlalchemy.exc.OperationalError)
async def operational_error_handler(request: Request, exc: sqlalchemy.exc.OperationalError):
    logger.error("Database connection error (%s)", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database temporarily unavailable"},
    )


@app.exception_handler(sqlalchemy.exc.SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: sqlalchemy.exc.SQLAlchemyError):
    logger.error("Database error (%s)", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception (%s)", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )



@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers and handle HTTPS redirect."""
    # HTTPS redirect in production
    proto = request.headers.get("x-forwarded-proto", "")
    if proto == "http" and settings.ENVIRONMENT == "production":
        url = request.url.replace(scheme="https")
        return RedirectResponse(url=str(url), status_code=301)

    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    if settings.ENVIRONMENT != "development":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Idempotency-Key"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"name": settings.PROJECT_NAME, "version": settings.APP_VERSION}
