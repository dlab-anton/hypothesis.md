import uuid

from fastapi import APIRouter, Path, Query, Request, Security
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from ....core.exceptions import HypothesisEngineError, ValidationError
from ....core.security import api_key_header_auth, authenticate_api_key
from ....db.database import SessionLocal
from ....schemas.channel_context import ChannelContextResponse
from ....schemas.common import normalize_channel
from ....services.channel_context_service import read_channel_context


class NoStoreRoute(APIRoute):
    """Keep every response from this private context endpoint non-cacheable."""

    def get_route_handler(self):
        route_handler = super().get_route_handler()

        async def no_store_handler(request: Request) -> Response:
            try:
                response = await route_handler(request)
            except HypothesisEngineError as exc:
                response = JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": exc.detail},
                )
            except RequestValidationError as exc:
                response = await request_validation_exception_handler(request, exc)
            except StarletteHTTPException as exc:
                response = await http_exception_handler(request, exc)
            except Exception:
                response = JSONResponse(
                    status_code=500,
                    content={"detail": "Unable to read channel context"},
                )
            response.headers["Cache-Control"] = "no-store"
            return response

        return no_store_handler


router = APIRouter(tags=["channels"], route_class=NoStoreRoute)

_ALLOWED_QUERY_PARAMETERS = frozenset(
    {"expected_channel_id", "active_offset", "archived_offset", "insight_offset"}
)
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
    "/channels/{name}/context",
    response_model=ChannelContextResponse,
    summary="Read a bounded, consistent channel context",
)
async def get_channel_context(
    request: Request,
    name: str = Path(..., min_length=1, max_length=255),
    expected_channel_id: uuid.UUID = Query(...),
    active_offset: int = Query(0, ge=0, le=100_000),
    archived_offset: int = Query(0, ge=0, le=100_000),
    insight_offset: int = Query(0, ge=0, le=100_000),
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
        context = await read_channel_context(
            db,
            auth,
            name=normalized_name,
            expected_channel_id=expected_channel_id,
            active_offset=active_offset,
            archived_offset=archived_offset,
            insight_offset=insight_offset,
        )
        payload = context.model_dump_json().encode("utf-8")
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise HypothesisEngineError(
                detail="Channel context response exceeds the byte limit",
                status_code=413,
            )

    return Response(
        content=payload,
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )
