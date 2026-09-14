"""Atomic create replay at PostgreSQL READ COMMITTED isolation.

The unique insert waits for an in-flight owner to commit or roll back. A loser
then reads the committed response in a new statement snapshot. The caller must
persist the response and domain changes in one transaction, with one commit.
No expiry: deleting these records would remove the retry guarantee.
"""
import hashlib
import json
import uuid
from typing import Annotated

from fastapi import Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.idempotency import WriteIdempotency

IdempotencyKey = Annotated[str | None, Header(
    alias="Idempotency-Key", min_length=1, max_length=200, pattern=r"^[!-~]+$",
    description="Optional durable create identity, scoped to authenticated tenant and operation. "
                "Exact normalized payload retries return the original 201 body; changed payload returns 409.",
)]


async def reserve(
    db: AsyncSession, tenant_id: uuid.UUID, operation: str,
    key: str | None, payload: dict,
) -> tuple[uuid.UUID | None, dict | None]:
    if key is None:
        return None, None
    try:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Payload must contain finite JSON values") from exc
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    record_id = uuid.uuid4()
    result = await db.execute(insert(WriteIdempotency).values(
        id=record_id, tenant_id=tenant_id, operation=operation, key=key,
        payload_digest=digest,
    ).on_conflict_do_nothing(constraint="uq_write_idempotency_scope")
      .returning(WriteIdempotency.id))
    if result.scalar_one_or_none() is not None:
        return record_id, None
    record = (await db.execute(select(WriteIdempotency).where(
        WriteIdempotency.tenant_id == tenant_id,
        WriteIdempotency.operation == operation,
        WriteIdempotency.key == key,
    ))).scalar_one()
    if record.payload_digest != digest:
        raise HTTPException(status_code=409, detail="Idempotency-Key was already used with a different payload")
    if record.response is None:
        # An incomplete committed row is an invariant violation, never permission
        # to execute an ambiguous write again.
        raise HTTPException(status_code=503, detail="Idempotency result is unavailable; reconcile this delivery")
    return None, record.response


async def complete(db: AsyncSession, record_id: uuid.UUID | None, response: BaseModel) -> dict:
    body = response.model_dump(mode="json")
    if record_id is not None:
        await db.execute(update(WriteIdempotency).where(
            WriteIdempotency.id == record_id,
        ).values(response=body))
    return body
