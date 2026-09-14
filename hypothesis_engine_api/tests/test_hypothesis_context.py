import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints import hypothesis_context as endpoint_module
from app.core.config import settings
from app.crud.crud_api_key import hash_key
from app.db.database import engine as application_engine
from app.db.models.api_key import ApiKey
from app.db.models.channel import Channel
from app.db.models.evidence import Evidence
from app.db.models.hypothesis import Hypothesis
from app.main import app
from app.services import hypothesis_context_service

BASE = "/api/v1/channels"
FIXTURE = Path(__file__).parent / "fixtures" / "hypothesis-context-v1.json"
UTC = timezone.utc


async def _client(raw_key: str | None = None) -> AsyncClient:
    headers = {"X-API-Key": raw_key} if raw_key is not None else {}
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://synthetic",
        headers=headers,
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
    name = name or f"targeted-{uuid.uuid4().hex}"
    raw_key = raw_key or f"he_{uuid.uuid4().hex}"
    now = datetime(2026, 5, 1, tzinfo=UTC)
    async with AsyncSession(engine) as db:
        db.add_all([
            ApiKey(
                key_hash=hash_key(raw_key), key_prefix=raw_key[:10],
                label="targeted context test", tenant_id=tenant_id,
                last_used_at=None,
            ),
            Channel(
                id=channel_id, name=name, goal="Synthetic targeted context tests",
                created_by="test-agent", tenant_id=tenant_id,
                created_at=now, updated_at=now,
            ),
        ])
        await db.commit()
    return tenant_id, channel_id, name, raw_key


async def _add_hypothesis(
    engine,
    tenant_id: uuid.UUID,
    channel_name: str,
    *,
    hypothesis_id: uuid.UUID | None = None,
    archived: bool = False,
    statement: str = "targeted hypothesis",
) -> uuid.UUID:
    hypothesis_id = hypothesis_id or uuid.uuid4()
    async with AsyncSession(engine) as db:
        db.add(Hypothesis(
            id=hypothesis_id, tenant_id=tenant_id, channel=channel_name,
            statement=statement, status="draft", tags=[], created_by="test-agent",
            is_archived=archived,
        ))
        await db.commit()
    return hypothesis_id


async def _get(
    raw_key: str,
    name: str,
    channel_id: uuid.UUID,
    hypothesis_id: uuid.UUID,
    **params,
):
    query = {"expected_channel_id": str(channel_id), **params}
    async with await _client(raw_key) as client:
        return await client.get(
            f"{BASE}/{name}/context/hypotheses/{hypothesis_id}", params=query
        )


async def test_actual_route_matches_deterministic_fixture_and_is_read_only(
    engine, setup_database
):
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tenant_id = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    channel_id = uuid.UUID(expected["channel"]["id"])
    hypothesis_id = uuid.UUID(expected["hypothesis"]["id"])
    raw_key = "he_fixture_hypothesis_context_key"

    def timestamp(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    async with AsyncSession(engine) as db:
        db.add(ApiKey(
            id=uuid.UUID("bbbbbbbb-0000-4000-8000-000000000001"),
            key_hash=hash_key(raw_key), key_prefix=raw_key[:10],
            tenant_id=tenant_id, last_used_at=None,
        ))
        channel = expected["channel"]
        db.add(Channel(
            id=channel_id, name=channel["name"], goal=channel["goal"],
            created_by=channel["created_by"], tenant_id=tenant_id,
            created_at=timestamp(channel["created_at"]),
            updated_at=timestamp(channel["updated_at"]),
        ))
        item = expected["hypothesis"]
        db.add(Hypothesis(
            id=hypothesis_id, statement=item["statement"], context=item["context"],
            falsification_criteria=item["falsification_criteria"],
            status=item["status"], confidence=item["confidence"],
            initial_confidence=item["initial_confidence"], tags=item["tags"],
            created_by=item["created_by"], is_archived=item["is_archived"],
            metadata_=item["metadata"], null_hypothesis=item["null_hypothesis"],
            experimental_design=item["experimental_design"],
            significance_level=item["significance_level"], outcome=item["outcome"],
            channel=item["channel"], tenant_id=tenant_id,
            created_at=timestamp(item["created_at"]),
            updated_at=timestamp(item["updated_at"]),
        ))
        await db.flush()
        for evidence in expected["evidence_page"]["items"]:
            db.add(Evidence(
                id=uuid.UUID(evidence["id"]), hypothesis_id=hypothesis_id,
                content=evidence["content"], source=evidence["source"],
                evidence_type=evidence["evidence_type"], strength=evidence["strength"],
                confidence_after=evidence["confidence_after"],
                created_by=evidence["created_by"],
                created_at=timestamp(evidence["created_at"]),
                updated_at=timestamp(evidence["created_at"]),
            ))
        await db.commit()

    statements: list[str] = []

    def record_query(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(application_engine.sync_engine, "before_cursor_execute", record_query)
    try:
        response = await _get(
            raw_key, "Synthetic Targeted Context", channel_id, hypothesis_id
        )
    finally:
        event.remove(
            application_engine.sync_engine, "before_cursor_execute", record_query
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == expected
    reads = [statement for statement in statements
             if statement.lstrip().upper().startswith(("SELECT", "WITH"))]
    assert len(reads) == 5
    assert not any(statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                   for statement in statements)
    async with AsyncSession(engine) as db:
        key = await db.scalar(
            select(ApiKey).where(ApiKey.key_hash == hash_key(raw_key))
        )
        assert key is not None and key.last_used_at is None


async def test_workspace_master_archive_and_hypothesis_scope(engine, setup_database):
    tenant_a, channel_a, name, key_a = await _workspace(engine)
    tenant_b, channel_b, _, key_b = await _workspace(engine, name=name)
    _, other_channel, other_name, _ = await _workspace(engine, tenant_id=tenant_b)
    hypothesis_a = await _add_hypothesis(engine, tenant_a, name, statement="tenant-a")
    hypothesis_b = await _add_hypothesis(
        engine, tenant_b, name, archived=True, statement="tenant-b archived"
    )
    other_hypothesis = await _add_hypothesis(engine, tenant_b, other_name)

    own = await _get(key_a, name, channel_a, hypothesis_a)
    rebound = await _get(key_a, name, channel_b, hypothesis_a)
    foreign_hypothesis = await _get(key_a, name, channel_a, hypothesis_b)
    same_tenant_other_channel = await _get(
        key_b, name, channel_b, other_hypothesis
    )
    archived = await _get(key_b, name, channel_b, hypothesis_b)
    master = await _get(settings.API_MASTER_KEY, name, channel_b, hypothesis_b)
    master_wrong_channel = await _get(
        settings.API_MASTER_KEY, name, other_channel, other_hypothesis
    )
    missing = await _get(key_a, name, channel_a, uuid.uuid4())
    invalid_key = await _get("he_invalid_targeted_key", name, channel_a, hypothesis_a)
    async with await _client() as client:
        anonymous = await client.get(
            f"{BASE}/{name}/context/hypotheses/{hypothesis_a}",
            params={"expected_channel_id": str(channel_a)},
        )

    assert own.status_code == 200
    assert rebound.status_code == 409
    assert foreign_hypothesis.status_code == 404
    assert same_tenant_other_channel.status_code == 404
    assert archived.status_code == 200
    assert archived.json()["hypothesis"]["is_archived"] is True
    assert master.status_code == 200
    assert master.json()["hypothesis"]["statement"] == "tenant-b archived"
    assert master_wrong_channel.status_code == 404
    assert missing.status_code == 404
    assert invalid_key.status_code == 401
    assert anonymous.status_code == 403
    assert all(response.headers["cache-control"] == "no-store" for response in (
        own, rebound, foreign_hypothesis, same_tenant_other_channel, archived, master,
        master_wrong_channel, missing, invalid_key, anonymous,
    ))


async def test_query_shape_and_bounds_are_strict(engine, setup_database):
    tenant_id, channel_id, name, raw_key = await _workspace(engine)
    hypothesis_id = await _add_hypothesis(engine, tenant_id, name)
    base = f"{BASE}/{name}/context/hypotheses/{hypothesis_id}"
    queries = [
        "",
        f"?expected_channel_id={channel_id}&unknown=1",
        f"?expected_channel_id={channel_id}&expected_channel_id={channel_id}",
        f"?expected_channel_id={channel_id}&evidence_offset=0&evidence_offset=0",
        f"?expected_channel_id={channel_id}&evidence_offset=-1",
        f"?expected_channel_id={channel_id}&evidence_offset=100001",
        f"?expected_channel_id={channel_id}&evidence_offset=1.5",
    ]
    async with await _client(raw_key) as client:
        responses = [await client.get(f"{base}{query}") for query in queries]
        invalid_path = await client.get(
            f"{BASE}/{name}/context/hypotheses/not-a-uuid",
            params={"expected_channel_id": str(channel_id)},
        )
    assert all(response.status_code == 422 for response in [*responses, invalid_path])
    assert all(response.headers["cache-control"] == "no-store"
               for response in [*responses, invalid_path])


async def test_evidence_offset_order_counts_and_beyond_end(engine, setup_database):
    tenant_id, channel_id, name, raw_key = await _workspace(engine)
    hypothesis_id = await _add_hypothesis(engine, tenant_id, name)
    base_time = datetime(2026, 5, 3, 4, 5, 6, tzinfo=UTC)
    evidence_rows: list[tuple[uuid.UUID, datetime, str]] = []
    async with AsyncSession(engine) as db:
        for index in range(25):
            item_id = uuid.UUID(f"{index + 1:08x}-0000-4000-8000-000000000001")
            timestamp = base_time.replace(microsecond=index + 1)
            kind = ("supporting", "contradicting", "neutral")[index % 3]
            evidence_rows.append((item_id, timestamp, kind))
            db.add(Evidence(
                id=item_id, hypothesis_id=hypothesis_id, content=f"item-{index}",
                evidence_type=kind, created_by="test-agent",
                created_at=timestamp, updated_at=timestamp,
            ))
        await db.commit()
    expected = [str(row[0]) for row in sorted(
        evidence_rows, key=lambda row: (row[1], row[0]), reverse=True
    )]

    first = await _get(raw_key, name, channel_id, hypothesis_id)
    tail = await _get(
        raw_key, name, channel_id, hypothesis_id, evidence_offset=20
    )
    beyond = await _get(
        raw_key, name, channel_id, hypothesis_id, evidence_offset=100_000
    )
    assert [
        item["id"] for item in first.json()["evidence_page"]["items"]
    ] == expected[:20]
    assert [
        item["id"] for item in tail.json()["evidence_page"]["items"]
    ] == expected[20:]
    assert tail.json()["evidence_page"] | {"items": []} == {
        "hypothesis_id": str(hypothesis_id), "items": [],
        "total": 25, "offset": 20, "limit": 20,
    }
    assert beyond.json()["evidence_page"] == {
        "hypothesis_id": str(hypothesis_id), "items": [],
        "total": 25, "offset": 100_000, "limit": 20,
    }
    assert first.json()["hypothesis"]["evidence_counts"] == {
        "supporting": 9, "contradicting": 8, "neutral": 8,
    }


async def test_repeatable_read_excludes_independently_committed_edit(
    engine, setup_database, monkeypatch
):
    tenant_id, channel_id, name, raw_key = await _workspace(engine)
    hypothesis_id = await _add_hypothesis(engine, tenant_id, name, statement="before")
    evidence_id = uuid.uuid4()
    async with AsyncSession(engine) as db:
        db.add(Evidence(
            id=evidence_id, hypothesis_id=hypothesis_id, content="before",
            evidence_type="neutral", created_by="test-agent",
        ))
        await db.commit()
    baseline = await _get(raw_key, name, channel_id, hypothesis_id)
    assert baseline.status_code == 200

    hypothesis_read = asyncio.Event()
    writer_committed = asyncio.Event()
    original = hypothesis_context_service._hypothesis_for_request

    async def read_then_pause(*args, **kwargs):
        result = await original(*args, **kwargs)
        hypothesis_read.set()
        await asyncio.wait_for(writer_committed.wait(), timeout=5)
        return result

    monkeypatch.setattr(
        hypothesis_context_service, "_hypothesis_for_request", read_then_pause
    )
    try:
        async with await _client(raw_key) as client:
            request = asyncio.create_task(client.get(
                f"{BASE}/{name}/context/hypotheses/{hypothesis_id}",
                params={"expected_channel_id": str(channel_id)},
            ))
            await asyncio.wait_for(hypothesis_read.wait(), timeout=5)
            async with AsyncSession(engine) as writer:
                await writer.execute(update(Hypothesis).where(
                    Hypothesis.id == hypothesis_id
                ).values(statement="after"))
                await writer.execute(update(Evidence).where(
                    Evidence.id == evidence_id
                ).values(content="after", evidence_type="supporting"))
                writer.add(Evidence(
                    hypothesis_id=hypothesis_id, content="new evidence",
                    evidence_type="contradicting", created_by="test-agent",
                ))
                await writer.commit()
            writer_committed.set()
            first = await asyncio.wait_for(request, timeout=5)
    finally:
        monkeypatch.setattr(
            hypothesis_context_service, "_hypothesis_for_request", original
        )
    assert first.status_code == 200
    assert first.json() == baseline.json()
    second = await _get(raw_key, name, channel_id, hypothesis_id)
    assert second.json()["hypothesis"]["statement"] == "after"
    assert second.json()["hypothesis"]["evidence_counts"] == {
        "supporting": 1, "contradicting": 1, "neutral": 0,
    }
    assert {item["content"] for item in second.json()["evidence_page"]["items"]} == {
        "after", "new evidence",
    }


async def test_exact_utf8_cap_and_redacted_failure(
    engine, setup_database, monkeypatch
):
    tenant_id, channel_id, name, raw_key = await _workspace(engine)
    hypothesis_id = await _add_hypothesis(engine, tenant_id, name)
    fixed_time = datetime(2026, 5, 4, tzinfo=UTC)

    async def set_padding(padding: str):
        async with AsyncSession(engine) as db:
            await db.execute(update(Channel).where(Channel.id == channel_id).values(
                metadata_={"padding": padding}, updated_at=fixed_time,
            ))
            await db.commit()

    await set_padding("")
    base = await _get(raw_key, name, channel_id, hypothesis_id)
    remaining = 524_288 - len(base.content)
    unicode_count, remainder = divmod(remaining, len("界".encode("utf-8")))
    padding = "界" * unicode_count + "x" * remainder
    await set_padding(padding)
    at_limit = await _get(raw_key, name, channel_id, hypothesis_id)
    assert at_limit.status_code == 200
    assert len(at_limit.content) == 524_288
    assert at_limit.headers["cache-control"] == "no-store"
    await set_padding(padding + "x")
    too_large = await _get(raw_key, name, channel_id, hypothesis_id)
    assert too_large.status_code == 413
    assert too_large.json() == {
        "detail": "Hypothesis context response exceeds the byte limit"
    }
    assert too_large.headers["cache-control"] == "no-store"

    async def fail_read(*_args, **_kwargs):
        raise RuntimeError("SECRET targeted database diagnostic")

    monkeypatch.setattr(endpoint_module, "read_hypothesis_context", fail_read)
    failed = await _get(raw_key, name, channel_id, hypothesis_id)
    assert failed.status_code == 500
    assert failed.headers["cache-control"] == "no-store"
    assert failed.json() == {"detail": "Unable to read channel context"}
    assert "SECRET" not in failed.text
