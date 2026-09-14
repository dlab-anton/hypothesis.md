import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints import channel_context as endpoint_module
from app.core.config import settings
from app.core.security import get_api_key
from app.crud.crud_api_key import hash_key
from app.db.database import engine as application_engine
from app.db.models.api_key import ApiKey
from app.db.models.channel import Channel
from app.db.models.evidence import Evidence
from app.db.models.hypothesis import Hypothesis
from app.db.models.insight import Insight
from app.main import app
from app.services import channel_context_service

BASE = "/api/v1/channels"
FIXTURE = Path(__file__).parent / "fixtures" / "channel-context-v1.json"
UTC = timezone.utc


async def _client(raw_key: str) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://synthetic",
        headers={"X-API-Key": raw_key},
    )


async def _workspace(
    engine,
    *,
    tenant_id: uuid.UUID | None = None,
    channel_id: uuid.UUID | None = None,
    name: str | None = None,
    raw_key: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID, str, str]:
    tenant_id = tenant_id or uuid.uuid4()
    channel_id = channel_id or uuid.uuid4()
    name = name or f"context-{uuid.uuid4().hex}"
    raw_key = raw_key or f"he_{uuid.uuid4().hex}"
    now = datetime(2026, 2, 1, tzinfo=UTC)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        db.add_all(
            [
                ApiKey(
                    key_hash=hash_key(raw_key),
                    key_prefix=raw_key[:10],
                    label="context test",
                    tenant_id=tenant_id,
                    last_used_at=None,
                ),
                Channel(
                    id=channel_id,
                    name=name,
                    goal="Synthetic context tests",
                    created_by="test-agent",
                    tenant_id=tenant_id,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await db.commit()
    return tenant_id, channel_id, name, raw_key


async def _get(raw_key: str, name: str, channel_id: uuid.UUID, **params):
    query = {"expected_channel_id": str(channel_id), **params}
    async with await _client(raw_key) as client:
        return await client.get(f"{BASE}/{name}/context", params=query)


async def test_actual_route_matches_deterministic_fixture_and_does_not_touch_key(
    engine, setup_database
):
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tenant_id = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    channel_id = uuid.UUID(expected["channel"]["id"])
    raw_key = "he_fixture_channel_context_key"
    def timestamp(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    async with AsyncSession(engine) as db:
        db.add(
            ApiKey(
                id=uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001"),
                key_hash=hash_key(raw_key),
                key_prefix=raw_key[:10],
                tenant_id=tenant_id,
                last_used_at=None,
            )
        )
        channel = expected["channel"]
        db.add(
            Channel(
                id=channel_id,
                name=channel["name"],
                goal=channel["goal"],
                created_by=channel["created_by"],
                tenant_id=tenant_id,
                created_at=timestamp(channel["created_at"]),
                updated_at=timestamp(channel["updated_at"]),
            )
        )
        for page_name in ("active_hypotheses", "archived_hypotheses"):
            item = expected[page_name]["items"][0]
            db.add(
                Hypothesis(
                    id=uuid.UUID(item["id"]),
                    statement=item["statement"],
                    context=item["context"],
                    falsification_criteria=item["falsification_criteria"],
                    status=item["status"],
                    confidence=item["confidence"],
                    initial_confidence=item["initial_confidence"],
                    tags=item["tags"],
                    created_by=item["created_by"],
                    is_archived=item["is_archived"],
                    metadata_=item["metadata"],
                    null_hypothesis=item["null_hypothesis"],
                    experimental_design=item["experimental_design"],
                    significance_level=item["significance_level"],
                    outcome=item["outcome"],
                    channel=item["channel"],
                    tenant_id=tenant_id,
                    created_at=timestamp(item["created_at"]),
                    updated_at=timestamp(item["updated_at"]),
                )
            )
        insight = expected["insights"]["items"][0]
        db.add(
            Insight(
                id=uuid.UUID(insight["id"]),
                channel=insight["channel"],
                insight_type=insight["insight_type"],
                content=insight["content"],
                created_by=insight["created_by"],
                tenant_id=tenant_id,
                created_at=timestamp(insight["created_at"]),
                updated_at=timestamp(insight["updated_at"]),
            )
        )
        for page in expected["evidence_pages"]:
            item = page["items"][0]
            db.add(
                Evidence(
                    id=uuid.UUID(item["id"]),
                    hypothesis_id=uuid.UUID(item["hypothesis_id"]),
                    content=item["content"],
                    source=item["source"],
                    evidence_type=item["evidence_type"],
                    strength=item["strength"],
                    confidence_after=item["confidence_after"],
                    created_by=item["created_by"],
                    created_at=timestamp(item["created_at"]),
                    updated_at=timestamp(item["created_at"]),
                )
            )
        await db.commit()

    statements: list[str] = []

    def record_query(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(application_engine.sync_engine, "before_cursor_execute", record_query)
    try:
        response = await _get(raw_key, "Synthetic Context", channel_id)
    finally:
        event.remove(
            application_engine.sync_engine, "before_cursor_execute", record_query
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == expected
    reads = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith(("SELECT", "WITH"))
    ]
    assert len(reads) == 7
    assert not any(
        statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        for statement in statements
    )
    async with AsyncSession(engine) as db:
        key = await db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(raw_key)))
        assert key is not None and key.last_used_at is None


async def test_workspace_and_master_channel_identity_scope(engine, setup_database):
    tenant_a, channel_a, name, key_a = await _workspace(engine)
    tenant_b, channel_b, _, key_b = await _workspace(engine, name=name)
    _, other_channel, other_name, _ = await _workspace(engine, tenant_id=tenant_b)

    assert (await _get(key_a, name, channel_a)).status_code == 200
    assert (await _get(key_a, name, channel_b)).status_code == 409
    assert (await _get(key_a, other_name, other_channel)).status_code == 404
    assert (await _get(key_b, name, channel_b)).status_code == 200
    assert (
        await _get(settings.API_MASTER_KEY, name, channel_b)
    ).json()["channel"]["id"] == str(channel_b)
    assert (await _get(settings.API_MASTER_KEY, name, other_channel)).status_code == 404
    assert tenant_a != tenant_b


async def test_same_name_tenants_cannot_mix_research_or_counts(engine, setup_database):
    tenant_a, channel_a, name, key_a = await _workspace(engine)
    tenant_b, channel_b, _, key_b = await _workspace(engine, name=name)
    hypothesis_ids = [uuid.uuid4(), uuid.uuid4()]
    async with AsyncSession(engine) as db:
        for tenant_id, hypothesis_id, marker in (
            (tenant_a, hypothesis_ids[0], "tenant-a-only"),
            (tenant_b, hypothesis_ids[1], "tenant-b-only"),
        ):
            db.add(Hypothesis(
                id=hypothesis_id, tenant_id=tenant_id, channel=name,
                statement=marker, status="draft", tags=[],
                created_by=marker, is_archived=False,
            ))
            db.add(Insight(
                tenant_id=tenant_id, channel=name, insight_type="pattern",
                content=marker, created_by=marker,
            ))
        await db.flush()
        for hypothesis_id, marker in zip(
            hypothesis_ids, ("tenant-a-only", "tenant-b-only")
        ):
            db.add(Evidence(
                hypothesis_id=hypothesis_id, content=marker,
                evidence_type="neutral", created_by=marker,
            ))
        await db.commit()

    for key, channel_id, hypothesis_id, own, foreign in (
        (key_a, channel_a, hypothesis_ids[0], "tenant-a-only", "tenant-b-only"),
        (key_b, channel_b, hypothesis_ids[1], "tenant-b-only", "tenant-a-only"),
        (settings.API_MASTER_KEY, channel_b, hypothesis_ids[1],
         "tenant-b-only", "tenant-a-only"),
    ):
        response = await _get(key, name, channel_id)
        assert response.status_code == 200
        body = response.json()
        assert own in response.text and foreign not in response.text
        assert body["active_hypotheses"]["total"] == 1
        assert body["archived_hypotheses"]["total"] == 0
        assert body["insights"]["total"] == 1
        assert len(body["evidence_pages"]) == 1
        assert body["evidence_pages"][0]["hypothesis_id"] == str(hypothesis_id)
        assert body["evidence_pages"][0]["total"] == 1
        assert body["active_hypotheses"]["items"][0]["evidence_counts"] == {
            "supporting": 0, "contradicting": 0, "neutral": 1,
        }


async def test_revoked_context_key_is_denied_without_usage_write(engine, setup_database):
    _, channel_id, name, raw_key = await _workspace(engine)
    async with AsyncSession(engine) as db:
        await db.execute(update(ApiKey).where(
            ApiKey.key_hash == hash_key(raw_key)
        ).values(is_active=False))
        await db.commit()
    response = await _get(raw_key, name, channel_id)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "Invalid API key"}
    async with AsyncSession(engine) as db:
        key = await db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(raw_key)))
        assert key is not None and key.last_used_at is None and not key.is_active


async def test_pages_have_stable_tie_order_totals_offsets_and_empty_evidence(
    engine, setup_database
):
    tenant_id, channel_id, name, raw_key = await _workspace(engine)
    tied = datetime(2026, 3, 1, tzinfo=UTC)
    active_ids = sorted((uuid.uuid4() for _ in range(8)), reverse=True)
    archived_ids = sorted((uuid.uuid4() for _ in range(7)), reverse=True)
    insight_ids = sorted((uuid.uuid4() for _ in range(22)), reverse=True)
    async with AsyncSession(engine) as db:
        db.add_all(
            [
                Hypothesis(
                    id=item_id,
                    statement=f"active {item_id}",
                    status="draft",
                    tags=[],
                    created_by="test-agent",
                    is_archived=False,
                    channel=name,
                    tenant_id=tenant_id,
                    created_at=tied,
                    updated_at=tied,
                )
                for item_id in active_ids
            ]
            + [
                Hypothesis(
                    id=item_id,
                    statement=f"archived {item_id}",
                    status="inconclusive",
                    tags=[],
                    created_by="test-agent",
                    is_archived=True,
                    channel=name,
                    tenant_id=tenant_id,
                    created_at=tied,
                    updated_at=tied,
                )
                for item_id in archived_ids
            ]
            + [
                Insight(
                    id=item_id,
                    channel=name,
                    insight_type="pattern",
                    content=f"insight {item_id}",
                    created_by="test-agent",
                    tenant_id=tenant_id,
                    created_at=tied,
                    updated_at=tied,
                )
                for item_id in insight_ids
            ]
        )
        evidence_ids = sorted((uuid.uuid4() for _ in range(22)), reverse=True)
        db.add_all(
            [
                Evidence(
                    id=item_id,
                    hypothesis_id=active_ids[1],
                    content=f"evidence {item_id}",
                    evidence_type="neutral",
                    created_by="test-agent",
                    created_at=tied,
                    updated_at=tied,
                )
                for item_id in evidence_ids
            ]
        )
        await db.commit()

    statements: list[str] = []

    def record_query(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(application_engine.sync_engine, "before_cursor_execute", record_query)
    try:
        response = await _get(
            raw_key,
            name,
            channel_id,
            active_offset=1,
            archived_offset=1,
            insight_offset=1,
        )
    finally:
        event.remove(
            application_engine.sync_engine, "before_cursor_execute", record_query
        )
    assert response.status_code == 200
    body = response.json()
    assert body["active_hypotheses"]["total"] == 8
    assert [item["id"] for item in body["active_hypotheses"]["items"]] == [
        str(item_id) for item_id in active_ids[1:7]
    ]
    assert body["archived_hypotheses"]["total"] == 7
    assert [item["id"] for item in body["archived_hypotheses"]["items"]] == [
        str(item_id) for item_id in archived_ids[1:7]
    ]
    assert body["insights"]["total"] == 22
    assert [item["id"] for item in body["insights"]["items"]] == [
        str(item_id) for item_id in insight_ids[1:21]
    ]
    assert len(body["evidence_pages"]) == 12
    evidence_page = body["evidence_pages"][0]
    assert evidence_page["hypothesis_id"] == str(active_ids[1])
    assert evidence_page["total"] == 22
    assert [item["id"] for item in evidence_page["items"]] == [
        str(item_id) for item_id in evidence_ids[:20]
    ]
    assert all(
        page["items"] == [] and page["total"] == 0
        for page in body["evidence_pages"][1:]
    )
    assert sum(
        statement.lstrip().upper().startswith(("SELECT", "WITH"))
        for statement in statements
    ) == 7


@pytest.mark.parametrize(
    "query",
    [
        "expected_channel_id={id}&unexpected=true",
        "expected_channel_id={id}&expected_channel_id={id}",
        "expected_channel_id={id}&active_offset=-1",
        "expected_channel_id={id}&archived_offset=100001",
        "expected_channel_id={id}&insight_offset=not-an-int",
        "active_offset=0",
        "expected_channel_id=not-a-uuid",
    ],
)
async def test_query_contract_rejects_unknown_repeated_and_out_of_bounds(
    engine, setup_database, query
):
    _, channel_id, name, raw_key = await _workspace(engine)
    async with await _client(raw_key) as client:
        response = await client.get(
            f"{BASE}/{name}/context?{query.format(id=channel_id)}"
    )
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"


async def test_auth_and_lookup_errors_are_no_store(engine, setup_database):
    _, channel_id, name, raw_key = await _workspace(engine)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://synthetic"
    ) as client:
        missing_key = await client.get(
            f"{BASE}/{name}/context",
            params={"expected_channel_id": str(channel_id)},
        )
    missing_channel = await _get(raw_key, f"missing-{name}", channel_id)
    mismatch = await _get(raw_key, name, uuid.uuid4())
    invalid_key = await _get("he_invalid_context_key", name, channel_id)
    assert (
        missing_key.status_code,
        invalid_key.status_code,
        missing_channel.status_code,
        mismatch.status_code,
    ) == (
        403,
        401,
        404,
        409,
    )
    assert all(
        response.headers["cache-control"] == "no-store"
        for response in (missing_key, invalid_key, missing_channel, mismatch)
    )


async def test_unexpected_read_failure_is_fixed_redacted_and_no_store(
    engine, setup_database, monkeypatch
):
    _, channel_id, name, raw_key = await _workspace(engine)

    async def fail_read(*_args, **_kwargs):
        raise RuntimeError("SECRET internal database diagnostic")

    monkeypatch.setattr(endpoint_module, "read_channel_context", fail_read)
    response = await _get(raw_key, name, channel_id)
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "Unable to read channel context"}
    assert "SECRET" not in response.text


async def test_existing_auth_wrapper_still_touches_key_by_default(engine, setup_database):
    _, _, _, raw_key = await _workspace(engine)
    async with AsyncSession(engine) as db:
        auth = await get_api_key(raw_key, db)
        key = await db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(raw_key)))
        assert auth.is_master is False
        assert key is not None and key.last_used_at is not None


async def test_response_byte_cap_is_fixed_and_never_returns_partial_context(
    engine, setup_database
):
    tenant_id, channel_id, name, raw_key = await _workspace(engine)
    now = datetime(2026, 4, 1, tzinfo=UTC)
    hypotheses = [uuid.uuid4() for _ in range(6)]
    async with AsyncSession(engine) as db:
        db.add_all(
            [
                Hypothesis(
                    id=item_id,
                    statement=f"large {item_id}",
                    context="c" * 5000,
                    status="draft",
                    tags=[],
                    created_by="test-agent",
                    is_archived=False,
                    channel=name,
                    tenant_id=tenant_id,
                    created_at=now,
                    updated_at=now,
                )
                for item_id in hypotheses
            ]
        )
        await db.flush()
        db.add_all(
            [
                Evidence(
                    hypothesis_id=hypothesis_id,
                    content="e" * 5000,
                    evidence_type="neutral",
                    created_by="test-agent",
                    created_at=now,
                    updated_at=now,
                )
                for hypothesis_id in hypotheses
                for _ in range(20)
            ]
        )
        await db.commit()

    response = await _get(raw_key, name, channel_id)
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "Channel context response exceeds the byte limit"}
    assert "e" * 100 not in response.text


async def test_repeatable_read_excludes_independently_committed_concurrent_edit(
    engine, setup_database, monkeypatch
):
    tenant_id, channel_id, name, raw_key = await _workspace(engine)
    hypothesis_id, evidence_id, insight_id = [uuid.uuid4() for _ in range(3)]
    async with AsyncSession(engine) as db:
        db.add(Hypothesis(
            id=hypothesis_id, statement="before", status="draft", tags=[],
            created_by="test-agent", is_archived=False, channel=name,
            tenant_id=tenant_id,
        ))
        db.add(Insight(
            id=insight_id, content="before", insight_type="pattern",
            created_by="test-agent", channel=name, tenant_id=tenant_id,
        ))
        await db.flush()
        db.add(Evidence(
            id=evidence_id, hypothesis_id=hypothesis_id, content="before",
            evidence_type="neutral", created_by="test-agent",
        ))
        await db.commit()
    baseline = await _get(raw_key, name, channel_id)
    assert baseline.status_code == 200

    active_page_read = asyncio.Event()
    writer_committed = asyncio.Event()
    original = channel_context_service._hypotheses

    async def read_active_then_pause(*args, **kwargs):
        page = await original(*args, **kwargs)
        if not kwargs["archived"]:
            active_page_read.set()
            await asyncio.wait_for(writer_committed.wait(), timeout=5)
        return page

    monkeypatch.setattr(channel_context_service, "_hypotheses", read_active_then_pause)
    async with await _client(raw_key) as client:
        request = asyncio.create_task(
            client.get(
                f"{BASE}/{name}/context",
                params={"expected_channel_id": str(channel_id)},
            )
        )
        await asyncio.wait_for(active_page_read.wait(), timeout=5)
        async with AsyncSession(engine) as writer:
            await writer.execute(update(Channel).where(Channel.id == channel_id).values(
                goal="after", metadata_={"changed": True},
            ))
            await writer.execute(update(Hypothesis).where(
                Hypothesis.id == hypothesis_id
            ).values(statement="after"))
            await writer.execute(update(Insight).where(Insight.id == insight_id).values(
                content="after",
            ))
            await writer.execute(update(Evidence).where(Evidence.id == evidence_id).values(
                content="after", evidence_type="supporting",
            ))
            writer.add(Evidence(
                hypothesis_id=hypothesis_id, content="new evidence",
                evidence_type="contradicting", created_by="test-agent",
            ))
            writer.add(
                Hypothesis(
                    statement="concurrently committed",
                    status="draft",
                    tags=[],
                    created_by="test-agent",
                    is_archived=False,
                    channel=name,
                    tenant_id=tenant_id,
                )
            )
            await writer.commit()
        writer_committed.set()
        first = await asyncio.wait_for(request, timeout=5)

    assert first.status_code == 200
    assert first.json() == baseline.json()
    monkeypatch.setattr(channel_context_service, "_hypotheses", original)
    second = await _get(raw_key, name, channel_id)
    assert second.status_code == 200
    body = second.json()
    assert body["channel"]["goal"] == "after"
    assert body["channel"]["metadata"] == {"changed": True}
    assert body["active_hypotheses"]["total"] == 2
    hypothesis = next(item for item in body["active_hypotheses"]["items"]
                      if item["id"] == str(hypothesis_id))
    assert hypothesis["statement"] == "after"
    assert hypothesis["evidence_counts"] == {
        "supporting": 1, "contradicting": 1, "neutral": 0,
    }
    assert body["insights"]["items"][0]["content"] == "after"
    evidence_page = next(page for page in body["evidence_pages"]
                         if page["hypothesis_id"] == str(hypothesis_id))
    assert evidence_page["total"] == 2
    assert {item["content"] for item in evidence_page["items"]} == {
        "after", "new evidence",
    }


async def test_exact_utf8_response_cap_accepts_limit_and_rejects_one_extra_byte(
    engine, setup_database
):
    _, channel_id, name, raw_key = await _workspace(engine)
    fixed_time = datetime(2026, 4, 1, tzinfo=UTC)

    async def set_padding(padding: str):
        # Synthetic persisted read data exercises actual route serialization;
        # this does not assert that the public write schema accepts this size.
        async with AsyncSession(engine) as db:
            await db.execute(update(Channel).where(Channel.id == channel_id).values(
                metadata_={"padding": padding}, updated_at=fixed_time,
            ))
            await db.commit()

    await set_padding("")
    base = await _get(raw_key, name, channel_id)
    assert base.status_code == 200
    remaining_bytes = 524_288 - len(base.content)
    unicode_count, remainder = divmod(remaining_bytes, len("界".encode("utf-8")))
    padding = "界" * unicode_count + "x" * remainder
    await set_padding(padding)
    at_limit = await _get(raw_key, name, channel_id)
    assert at_limit.status_code == 200
    assert at_limit.headers["cache-control"] == "no-store"
    assert len(at_limit.content) == 524_288
    assert len(at_limit.text) < 524_288
    assert at_limit.json()["channel"]["metadata"]["padding"] == padding

    await set_padding(padding + "x")
    over_limit = await _get(raw_key, name, channel_id)
    assert over_limit.status_code == 413
    assert over_limit.headers["cache-control"] == "no-store"
    assert over_limit.json() == {"detail": "Channel context response exceeds the byte limit"}
    async with AsyncSession(engine) as db:
        key = await db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(raw_key)))
        assert key is not None and key.last_used_at is None
