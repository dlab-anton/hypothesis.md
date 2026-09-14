"""Real auth, independent transactions, synthetic data in runner-owned UUID DB."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import uuid

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.crud import crud_api_key, crud_hypothesis
from app.db.models import ApiKey, Evidence, Event, Hypothesis, Insight, WriteIdempotency
from app.main import app
from app.services import idempotency_service
from app.services import evidence_import_service

BASE = "/api/v1"
ACTOR = "motive:project:11111111-1111-4111-8111-111111111111"


@pytest.fixture
async def live_client(engine, setup_database):
    async def database():
        async with AsyncSession(engine, expire_on_commit=False) as db:
            try:
                yield db
            except Exception:
                await db.rollback()
                raise

    async with AsyncSession(engine, expire_on_commit=False) as db:
        key, raw = await crud_api_key.create_api_key(db, label="SYNTHETIC atomic tests")
        # Avoid serializing the concurrent test through last-used auth updates.
        key.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        tenant = key.tenant_id
        key_id = key.id
    app.dependency_overrides[get_db_session] = database
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://synthetic",
                               headers={"X-API-Key": raw}) as client:
            yield client, tenant, key_id
    finally:
        app.dependency_overrides.clear()


async def target(client, resource):
    if resource == "hypotheses":
        return BASE + "/hypotheses", {"statement": "SYNTHETIC unreviewed candidate", "created_by": ACTOR}
    if resource == "insights":
        return BASE + "/insights", {"channel": "synthetic", "insight_type": "pattern",
                                    "content": "SYNTHETIC unreviewed interpretation", "created_by": ACTOR}
    h = await client.post(BASE + "/hypotheses", json={
        "statement": "SYNTHETIC evidence target", "created_by": ACTOR, "confidence": 0.4})
    assert h.status_code == 201
    return BASE + f"/hypotheses/{h.json()['id']}/evidence", {
        "content": "SYNTHETIC observation only", "evidence_type": "neutral", "created_by": ACTOR,
        "source": "urn:synthetic:immutable-manifest:sha256:" + "a" * 64}


async def rows(engine, tenant):
    async with AsyncSession(engine) as db:
        return (await db.execute(select(WriteIdempotency).where(
            WriteIdempotency.tenant_id == tenant))).scalars().all()


async def blocking_pids(engine, pid):
    async with AsyncSession(engine) as db:
        return list(await db.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": pid}) or [])


async def wait_until_blocked(engine, pid):
    for _ in range(100):
        blockers = await blocking_pids(engine, pid)
        if blockers:
            return blockers
        await asyncio.sleep(0.02)
    raise AssertionError(f"PostgreSQL backend {pid} never waited on the target lock")


async def create_channel(client, name):
    response = await client.post(BASE + "/channels", json={
        "name": name,
        "goal": "SYNTHETIC channel identity test",
        "created_by": ACTOR,
    })
    assert response.status_code == 201
    return response.json()


async def channel_target(client, name="synthetic-channel"):
    channel = await create_channel(client, name)
    hypothesis = await client.post(BASE + "/hypotheses", json={
        "statement": "SYNTHETIC channel-bound evidence target",
        "created_by": ACTOR,
        "confidence": 0.4,
        "channel": name,
    })
    assert hypothesis.status_code == 201
    return (
        BASE + f"/hypotheses/{hypothesis.json()['id']}/evidence",
        {
            "content": "SYNTHETIC channel-bound observation",
            "evidence_type": "neutral",
            "created_by": ACTOR,
            "expected_channel_id": channel["id"],
        },
        hypothesis.json(),
        channel,
    )


@pytest.mark.parametrize("resource", ["hypotheses", "evidence", "insights"])
async def test_concurrent_exact_delivery_has_one_record_and_original_response(live_client, engine, monkeypatch, resource):
    client, tenant, _ = live_client
    path, payload = await target(client, resource)
    gate = asyncio.Barrier(6)
    original = idempotency_service.reserve

    async def simultaneous(*args, **kwargs):
        await gate.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(idempotency_service, "reserve", simultaneous)
    responses = await asyncio.wait_for(asyncio.gather(*(
        client.post(path, json=payload, headers={"Idempotency-Key": "concurrent"}) for _ in range(6)
    )), timeout=15)
    assert all(r.status_code == 201 for r in responses)
    assert all(r.json() == responses[0].json() for r in responses)
    assert len(await rows(engine, tenant)) == 1
    body = responses[0].json()
    async with AsyncSession(engine) as db:
        if resource == "evidence":
            assert await db.scalar(select(func.count()).select_from(Evidence).where(
                Evidence.hypothesis_id == uuid.UUID(body["hypothesis"]["id"]))) == 1
            assert await db.scalar(select(func.count()).select_from(Event).where(
                Event.hypothesis_id == uuid.UUID(body["hypothesis"]["id"]),
                Event.event_type == "evidence_added")) == 1
        else:
            model = Hypothesis if resource == "hypotheses" else Insight
            assert await db.scalar(select(func.count()).select_from(model).where(model.tenant_id == tenant)) == 1


@pytest.mark.parametrize("resource", ["hypotheses", "evidence", "insights"])
async def test_concurrent_changed_payload_conflicts(live_client, engine, resource):
    client, tenant, _ = live_client
    path, payload = await target(client, resource)
    changed = {**payload, ("statement" if resource == "hypotheses" else "content"): "SYNTHETIC changed"}
    results = await asyncio.gather(*(
        client.post(path, json=body, headers={"Idempotency-Key": "race"}) for body in (payload, changed)
    ))
    assert sorted(r.status_code for r in results) == [201, 409]
    assert len(await rows(engine, tenant)) == 1


@pytest.mark.parametrize("resource", ["hypotheses", "evidence", "insights"])
async def test_lost_response_replays_committed_snapshot_after_later_mutation(live_client, engine, resource):
    client, tenant, _ = live_client
    path, payload = await target(client, resource)

    async def lose_response(scope, receive, send):
        async def intercepted(message):
            if message["type"] == "http.response.start":
                raise RuntimeError("SYNTHETIC connection lost after commit")
            await send(message)
        await app(scope, receive, intercepted)

    async with AsyncClient(transport=ASGITransport(app=lose_response), base_url="http://synthetic",
                           headers=client.headers) as broken:
        with pytest.raises(RuntimeError, match="SYNTHETIC connection lost"):
            await broken.post(path, json=payload, headers={"Idempotency-Key": "lost"})
    records = await rows(engine, tenant)
    assert len(records) == 1
    original = records[0].response
    if resource == "insights":
        changed = await client.patch(BASE + "/insights/" + original["id"],
                                     json={"content": "SYNTHETIC later change", "updated_by": ACTOR})
    else:
        h = original["hypothesis"] if resource == "evidence" else original
        changed = await client.delete(BASE + "/hypotheses/" + h["id"])
    assert changed.status_code == 200
    replay = await client.post(path, json=payload, headers={"Idempotency-Key": "lost"})
    assert replay.status_code == 201
    assert replay.json() == original


@pytest.mark.parametrize("resource", ["hypotheses", "evidence", "insights"])
async def test_failed_transaction_rolls_back_domain_and_identity(live_client, engine, monkeypatch, resource):
    client, tenant, _ = live_client
    path, payload = await target(client, resource)
    original = idempotency_service.complete

    async def fail_after_response_record(*args, **kwargs):
        await original(*args, **kwargs)
        raise RuntimeError("SYNTHETIC failure before commit")

    monkeypatch.setattr(idempotency_service, "complete", fail_after_response_record)
    with pytest.raises(RuntimeError, match="SYNTHETIC failure before commit"):
        await client.post(path, json=payload, headers={"Idempotency-Key": "rollback"})
    assert await rows(engine, tenant) == []
    monkeypatch.setattr(idempotency_service, "complete", original)
    retry = await client.post(path, json=payload, headers={"Idempotency-Key": "rollback"})
    assert retry.status_code == 201
    assert len(await rows(engine, tenant)) == 1
    async with AsyncSession(engine) as db:
        if resource == "evidence":
            assert await db.scalar(select(func.count()).select_from(Evidence).where(
                Evidence.hypothesis_id == uuid.UUID(retry.json()["hypothesis"]["id"]))) == 1
        else:
            model = Hypothesis if resource == "hypotheses" else Insight
            assert await db.scalar(select(func.count()).select_from(model).where(model.tenant_id == tenant)) == 1


async def test_normalized_defaults_and_actor_filter(live_client):
    client, _, _ = live_client
    path, payload = await target(client, "hypotheses")
    payload.update(confidence=0.4, channel=" Synthetic Research ", tags=[" Test "],
                   metadata={"b": 2, "a": 1}, created_by=" " + ACTOR + " ")
    first = await client.post(path, json=payload, headers={"Idempotency-Key": "normalize"})
    normalized = {**payload, "created_by": ACTOR, "channel": "synthetic-research", "tags": ["test"],
                  "metadata": {"a": 1, "b": 2}, "initial_confidence": 0.4, "status": "draft", "context": None}
    replay = await client.post(path, json=normalized, headers={"Idempotency-Key": "normalize"})
    assert first.status_code == replay.status_code == 201
    assert replay.json() == first.json()
    filtered = await client.get(path, params={"created_by": ACTOR})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1


async def test_tenant_operation_and_target_scopes_and_current_auth(live_client, engine):
    client, tenant, key_id = live_client
    path, payload = await target(client, "hypotheses")
    headers = {"Idempotency-Key": "shared-human-key"}
    first = await client.post(path, json=payload, headers=headers)
    ipath, insight = await target(client, "insights")
    assert (await client.post(ipath, json=insight, headers=headers)).status_code == 201
    ep1, evidence = await target(client, "evidence")
    ep2, _ = await target(client, "evidence")
    assert (await client.post(ep1, json=evidence, headers=headers)).status_code == 201
    assert (await client.post(ep2, json=evidence, headers=headers)).status_code == 409
    async with AsyncSession(engine, expire_on_commit=False) as db:
        other, raw = await crud_api_key.create_api_key(db, label="SYNTHETIC other")
        other.last_used_at = datetime.now(timezone.utc)
        await db.commit()
    second = await client.post(path, json=payload, headers={**headers, "X-API-Key": raw})
    assert second.status_code == 201 and first.json()["id"] != second.json()["id"]
    assert (await client.post(ep1, json=evidence, headers={**headers, "X-API-Key": raw})).status_code == 404
    async with AsyncSession(engine) as db:
        await db.execute(update(ApiKey).where(ApiKey.id == key_id).values(is_active=False))
        await db.commit()
    assert (await client.post(path, json=payload, headers=headers)).status_code == 401
    assert (await client.post(ep1, json=evidence, headers=headers)).status_code == 401


@pytest.mark.parametrize("key", ["", "with space", "x" * 201])
async def test_invalid_delivery_key_is_rejected(live_client, key):
    client, _, _ = live_client
    path, payload = await target(client, "hypotheses")
    assert (await client.post(path, json=payload, headers={"Idempotency-Key": key})).status_code == 422


async def test_no_header_retains_create_semantics(live_client, engine):
    client, tenant, _ = live_client
    path, payload = await target(client, "hypotheses")
    first = await client.post(path, json=payload)
    second = await client.post(path, json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert await rows(engine, tenant) == []


@pytest.mark.parametrize("resource", ["hypotheses", "evidence", "insights"])
async def test_changed_attribution_conflicts_and_normalized_defaults_replay(live_client, resource):
    client, _, _ = live_client
    path, payload = await target(client, resource)
    first = await client.post(path, json=payload, headers={"Idempotency-Key": "actor"})
    normalized = {**payload, "created_by": " " + ACTOR + " "}
    if resource == "hypotheses":
        normalized.update(status="draft", tags=[], context=None)
    elif resource == "evidence":
        normalized.update(confidence=None, strength=None)
    else:
        normalized.update(metadata=None, channel=" SYNTHETIC ")
    replay = await client.post(path, json=normalized, headers={"Idempotency-Key": "actor"})
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    changed = await client.post(path, json={**payload, "created_by": "other-attribution"},
                                headers={"Idempotency-Key": "actor"})
    assert changed.status_code == 409


@pytest.mark.parametrize("resource", ["hypotheses", "evidence", "insights"])
async def test_concurrent_waiter_takes_over_rolled_back_delivery(live_client, engine, monkeypatch, resource):
    client, tenant, _ = live_client
    path, payload = await target(client, resource)
    before_commit = asyncio.Event()
    retry_started = asyncio.Event()
    original = idempotency_service.complete
    completion_count = 0

    async def first_fails(*args, **kwargs):
        nonlocal completion_count
        body = await original(*args, **kwargs)
        completion_count += 1
        if completion_count == 1:
            before_commit.set()
            await retry_started.wait()
            await asyncio.sleep(0.05)
            raise RuntimeError("SYNTHETIC first owner rolled back")
        return body

    monkeypatch.setattr(idempotency_service, "complete", first_fails)

    async def first():
        with pytest.raises(RuntimeError, match="SYNTHETIC first owner rolled back"):
            await client.post(path, json=payload, headers={"Idempotency-Key": "takeover"})

    async def second():
        await before_commit.wait()
        retry_started.set()
        return await client.post(path, json=payload, headers={"Idempotency-Key": "takeover"})

    _, retry = await asyncio.wait_for(asyncio.gather(first(), second()), timeout=15)
    assert retry.status_code == 201
    assert len(await rows(engine, tenant)) == 1


async def test_expected_channel_replays_after_move_and_changed_precondition_conflicts(live_client):
    client, _, _ = live_client
    path, payload, hypothesis, _ = await channel_target(client)
    other = await create_channel(client, "synthetic-other-channel")

    first = await client.post(path, json=payload, headers={"Idempotency-Key": "channel-replay"})
    assert first.status_code == 201
    moved = await client.patch(BASE + f"/hypotheses/{hypothesis['id']}", json={
        "channel": "synthetic-other-channel",
        "created_by": ACTOR,
    })
    assert moved.status_code == 200

    replay = await client.post(path, json=payload, headers={"Idempotency-Key": "channel-replay"})
    assert replay.status_code == 201
    assert replay.json() == first.json()

    wrong_channel = await client.post(path, json=payload, headers={"Idempotency-Key": "channel-new"})
    assert wrong_channel.status_code == 409
    changed_precondition = await client.post(
        path,
        json={**payload, "expected_channel_id": other["id"]},
        headers={"Idempotency-Key": "channel-replay"},
    )
    assert changed_precondition.status_code == 409


async def test_expected_channel_rejects_mismatch_null_and_same_name_replacement(live_client, engine):
    client, tenant, _ = live_client
    path, payload, hypothesis, channel = await channel_target(client, "synthetic-replaced-channel")
    mismatch = await create_channel(client, "synthetic-mismatch-channel")

    wrong = await client.post(
        path,
        json={**payload, "expected_channel_id": mismatch["id"]},
        headers={"Idempotency-Key": "channel-mismatch"},
    )
    assert wrong.status_code == 409
    explicit_null = await client.post(
        path,
        json={**payload, "expected_channel_id": None},
        headers={"Idempotency-Key": "channel-null"},
    )
    assert explicit_null.status_code == 422
    async with AsyncSession(engine) as db:
        hypothesis_id = uuid.UUID(hypothesis["id"])
        assert await db.scalar(select(func.count()).select_from(Evidence).where(
            Evidence.hypothesis_id == hypothesis_id)) == 0
        assert await db.scalar(select(func.count()).select_from(Event).where(
            Event.hypothesis_id == hypothesis_id,
            Event.event_type == "evidence_added")) == 0
        assert await db.scalar(select(Hypothesis.confidence).where(
            Hypothesis.id == hypothesis_id)) == 0.4
    assert not {"channel-mismatch", "channel-null"} & {row.key for row in await rows(engine, tenant)}

    deleted = await client.delete(BASE + "/channels/synthetic-replaced-channel")
    assert deleted.status_code == 204
    replacement = await create_channel(client, "synthetic-replaced-channel")
    assert replacement["id"] != channel["id"]
    stale_identity = await client.post(
        path, json=payload, headers={"Idempotency-Key": "channel-replaced"},
    )
    assert stale_identity.status_code == 409
    current_identity = await client.post(
        path,
        json={**payload, "expected_channel_id": replacement["id"]},
        headers={"Idempotency-Key": "channel-current"},
    )
    assert current_identity.status_code == 201


async def test_omitted_channel_preserves_legacy_digest_and_replay(live_client, engine):
    client, tenant, _ = live_client
    path, payload = await target(client, "evidence")
    first = await client.post(path, json=payload, headers={"Idempotency-Key": "legacy-evidence"})
    replay = await client.post(path, json={**payload, "strength": None, "confidence": None, "source": payload["source"]},
                               headers={"Idempotency-Key": "legacy-evidence"})
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()

    target_id = path.split("/")[-2]
    normalized = {**payload, "strength": None, "confidence": None}
    canonical = json.dumps(
        {"hypothesis_id": target_id, "evidence": normalized},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    expected_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    record = next(row for row in await rows(engine, tenant) if row.key == "legacy-evidence")
    assert record.payload_digest == expected_digest


async def test_target_move_waits_for_locked_channel_checked_import(live_client, engine, monkeypatch):
    client, _, _ = live_client
    path, payload, hypothesis, _ = await channel_target(client, "synthetic-race-source")
    await create_channel(client, "synthetic-race-destination")
    target_locked = asyncio.Event()
    release_import = asyncio.Event()
    move_backend = asyncio.Future()
    original_lock = evidence_import_service.lock_evidence_target
    original_update = crud_hypothesis.update_hypothesis

    async def hold_after_lock(*args, **kwargs):
        locked = await original_lock(*args, **kwargs)
        target_locked.set()
        await release_import.wait()
        return locked

    async def observe_move(db, target_hypothesis, **kwargs):
        if kwargs.get("channel") == "synthetic-race-destination" and not move_backend.done():
            move_backend.set_result(await db.scalar(text("SELECT pg_backend_pid()")))
        return await original_update(db, target_hypothesis, **kwargs)

    monkeypatch.setattr(evidence_import_service, "lock_evidence_target", hold_after_lock)
    monkeypatch.setattr(crud_hypothesis, "update_hypothesis", observe_move)

    import_task = asyncio.create_task(client.post(
        path, json=payload, headers={"Idempotency-Key": "channel-race"},
    ))
    await asyncio.wait_for(target_locked.wait(), timeout=5)
    move_task = asyncio.create_task(client.patch(
        BASE + f"/hypotheses/{hypothesis['id']}",
        json={"channel": "synthetic-race-destination", "created_by": ACTOR},
    ))
    try:
        move_pid = await asyncio.wait_for(move_backend, timeout=5)
        assert await asyncio.wait_for(wait_until_blocked(engine, move_pid), timeout=5)
    finally:
        release_import.set()
        results = await asyncio.wait_for(
            asyncio.gather(import_task, move_task, return_exceptions=True), timeout=10,
        )
    imported, moved = results
    assert not isinstance(imported, BaseException)
    assert not isinstance(moved, BaseException)
    assert imported.status_code == 201
    assert moved.status_code == 200
    assert moved.json()["channel"] == "synthetic-race-destination"
    async with AsyncSession(engine) as db:
        assert await db.scalar(select(func.count()).select_from(Evidence).where(
            Evidence.hypothesis_id == uuid.UUID(hypothesis["id"]))) == 1


async def test_distinct_targets_in_one_channel_check_concurrently(live_client, monkeypatch):
    client, _, _ = live_client
    first_path, first_payload, _, channel = await channel_target(client, "synthetic-shared-channel")
    second_hypothesis = await client.post(BASE + "/hypotheses", json={
        "statement": "SYNTHETIC second target in shared channel",
        "created_by": ACTOR,
        "channel": "synthetic-shared-channel",
    })
    assert second_hypothesis.status_code == 201
    second_path = BASE + f"/hypotheses/{second_hypothesis.json()['id']}/evidence"
    second_payload = {
        **first_payload,
        "content": "SYNTHETIC concurrent observation for the second target",
        "expected_channel_id": channel["id"],
    }
    both_channel_checks_held = asyncio.Barrier(2)
    original_lock = evidence_import_service.lock_evidence_target

    async def meet_after_shared_lock(*args, **kwargs):
        target = await original_lock(*args, **kwargs)
        await both_channel_checks_held.wait()
        return target

    monkeypatch.setattr(evidence_import_service, "lock_evidence_target", meet_after_shared_lock)
    first, second = await asyncio.wait_for(asyncio.gather(
        client.post(first_path, json=first_payload, headers={"Idempotency-Key": "shared-channel-first"}),
        client.post(second_path, json=second_payload, headers={"Idempotency-Key": "shared-channel-second"}),
    ), timeout=10)
    assert first.status_code == second.status_code == 201


async def test_import_rechecks_channel_after_waiting_for_move_lock(live_client, engine, monkeypatch):
    client, tenant, _ = live_client
    path, payload, hypothesis, _ = await channel_target(client, "synthetic-move-first-source")
    await create_channel(client, "synthetic-move-first-destination")
    move_locked = asyncio.Event()
    release_move = asyncio.Event()
    import_backend = asyncio.Future()
    original_lock = evidence_import_service.lock_evidence_target
    original_update = crud_hypothesis.update_hypothesis

    async def hold_move_lock(db, target_hypothesis, **kwargs):
        updated = await original_update(db, target_hypothesis, **kwargs)
        if kwargs.get("channel") == "synthetic-move-first-destination":
            move_locked.set()
            await release_move.wait()
        return updated

    async def observe_import(db, *args, **kwargs):
        if not import_backend.done():
            import_backend.set_result(await db.scalar(text("SELECT pg_backend_pid()")))
        return await original_lock(db, *args, **kwargs)

    monkeypatch.setattr(crud_hypothesis, "update_hypothesis", hold_move_lock)
    monkeypatch.setattr(evidence_import_service, "lock_evidence_target", observe_import)
    move_task = asyncio.create_task(client.patch(
        BASE + f"/hypotheses/{hypothesis['id']}",
        json={"channel": "synthetic-move-first-destination", "created_by": ACTOR},
    ))
    await asyncio.wait_for(move_locked.wait(), timeout=5)
    import_task = asyncio.create_task(client.post(
        path, json=payload, headers={"Idempotency-Key": "move-first-import"},
    ))
    try:
        import_pid = await asyncio.wait_for(import_backend, timeout=5)
        assert await asyncio.wait_for(wait_until_blocked(engine, import_pid), timeout=5)
    finally:
        release_move.set()
        results = await asyncio.wait_for(
            asyncio.gather(move_task, import_task, return_exceptions=True), timeout=10,
        )
    moved, imported = results
    assert not isinstance(moved, BaseException)
    assert not isinstance(imported, BaseException)
    assert moved.status_code == 200
    assert imported.status_code == 409
    assert "move-first-import" not in {row.key for row in await rows(engine, tenant)}
    async with AsyncSession(engine) as db:
        hypothesis_id = uuid.UUID(hypothesis["id"])
        assert await db.scalar(select(func.count()).select_from(Evidence).where(
            Evidence.hypothesis_id == hypothesis_id)) == 0
        assert await db.scalar(select(func.count()).select_from(Event).where(
            Event.hypothesis_id == hypothesis_id,
            Event.event_type == "evidence_added")) == 0
