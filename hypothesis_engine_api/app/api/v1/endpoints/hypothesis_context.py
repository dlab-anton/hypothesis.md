import uuid

from fastapi import APIRouter, Path, Query, Request, Security
from fastapi.responses import Response
from sqlalchemy import text

from ....core.exceptions import HypothesisEngineError, ValidationError
from ....core.security import api_key_header_auth, authenticate_api_key
from ....db.database import SessionLocal
from ....schemas.common import normalize_channel
from ....schemas.hypothesis_context import HypothesisContextResponse
from ....services.hypothesis_context_service import read_hypothesis_context
from .channel_context import NoStoreRoute

router = APIRouter(tags=["channels"], route_class=NoStoreRoute)

_ALLOWED_QUERY_PARAMETERS = frozenset({"expected_channel_id", "evidence_offset"})
_MAX_RESPONSE_BYTES = 524_288


def _validate_query_shape(request: Request) -> None:
    occurrences: dict[str, int] = {}
    for key, _ in request.query_params.multi_items():
        occurrences[key] = occurrences.get(key, 0) + 1
    if set(occurrences) - _ALLOWED_QUERY_PARAMETERS:
        raise ValidationError("Unknown query parameter")
    if any(count != 1 for count in occurrences.values()):
        raise ValidationError("Repeated query parameter")


@router.get(
    "/channels/{name}/context/hypotheses/{hypothesis_id}",
    response_model=HypothesisContextResponse,
    summary="Read one hypothesis and a bounded evidence page",
)
async def get_hypothesis_context(
    request: Request,
    name: str = Path(..., min_length=1, max_length=255),
    hypothesis_id: uuid.UUID = Path(...),
    expected_channel_id: uuid.UUID = Query(...),
    evidence_offset: int = Query(0, ge=0, le=100_000),
    api_key_header: str = Security(api_key_header_auth),
) -> Response:
    _validate_query_shape(request)
    normalized_name = normalize_channel(name) or name

    async with SessionLocal() as db:
        await db.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        )
        auth = await authenticate_api_key(
            api_key_header, db, touch_last_used=False
        )
        context = await read_hypothesis_context(
            db,
            auth,
            name=normalized_name,
            expected_channel_id=expected_channel_id,
            hypothesis_id=hypothesis_id,
            evidence_offset=evidence_offset,
        )
        payload = context.model_dump_json().encode("utf-8")
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise HypothesisEngineError(
                detail="Hypothesis context response exceeds the byte limit",
                status_code=413,
            )

    return Response(
        content=payload,
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )
