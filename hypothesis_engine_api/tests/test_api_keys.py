"""API integration tests for API key generation and management."""

import asyncio
import uuid

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.models.api_key import ApiKey

API_KEYS = "/api/v1/keys"
MASTER_HEADERS = {"X-API-Key": settings.API_MASTER_KEY}


async def wait_for_database_lock(sessions, pid: int) -> None:
    """Observe a real PostgreSQL lock wait rather than relying on elapsed time."""
    async with sessions() as observer:
        for _ in range(200):
            waiting = await observer.scalar(
                text(
                    "SELECT wait_event_type='Lock' FROM pg_stat_activity "
                    "WHERE pid=:pid AND state='active'"
                ),
                {"pid": pid},
            )
            if waiting is True:
                return
            await asyncio.sleep(0.01)
    raise AssertionError("Expected PostgreSQL lock wait was not observed")


@pytest.fixture(autouse=True)
async def isolated_key_generation_rate_limit():
    """Keep the real per-IP limit while isolating each test's request history."""
    from app.api.v1.endpoints.keys import _rate_lock, _rate_log

    async with _rate_lock:
        _rate_log.clear()
    yield
    async with _rate_lock:
        _rate_log.clear()


# ── POST /keys (generate — no auth) ─────────────────────────────

class TestGenerateKey:
    async def test_generate_key_returns_full_key(self, client: AsyncClient):
        resp = await client.post(API_KEYS, json={})
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"].startswith("he_")
        assert len(data["key"]) > 10
        assert data["prefix"] == data["key"][:10]
        assert data["created_at"] is not None
        assert resp.headers["Cache-Control"] == "no-store"
        # Should include an auto-generated tenant_id
        assert "tenant_id" in data
        assert data["tenant_id"] is not None

    async def test_generate_key_with_label(self, client: AsyncClient):
        resp = await client.post(API_KEYS, json={"label": "my-agent"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["label"] == "my-agent"

    async def test_generate_key_without_label(self, client: AsyncClient):
        resp = await client.post(API_KEYS, json={})
        assert resp.status_code == 201
        data = resp.json()
        assert data["label"] is None

    async def test_generate_key_no_body(self, client: AsyncClient):
        """POST with empty body should work (label is optional)."""
        resp = await client.post(API_KEYS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"].startswith("he_")

    async def test_each_key_unique(self, client: AsyncClient):
        keys = set()
        for _ in range(5):
            resp = await client.post(API_KEYS, json={})
            assert resp.status_code == 201
            keys.add(resp.json()["key"])
        assert len(keys) == 5

    async def test_generation_rate_limit_is_enforced(self, client: AsyncClient):
        for _ in range(5):
            assert (await client.post(API_KEYS, json={})).status_code == 201
        limited = await client.post(API_KEYS, json={})
        assert limited.status_code == 429
        assert limited.json() == {"detail": "Rate limit exceeded. Try again later."}
        assert limited.headers["X-RateLimit-Limit"] == "5"
        assert limited.headers["X-RateLimit-Remaining"] == "0"

    async def test_existing_workspace_requires_active_same_workspace_key(
        self, client: AsyncClient
    ):
        original = (await client.post(API_KEYS, json={"label": "original"})).json()
        target = {"tenant_id": original["tenant_id"], "label": "child"}

        missing = await client.post(API_KEYS, json=target)
        invalid = await client.post(
            API_KEYS,
            json=target,
            headers={"X-API-Key": "he_not_a_real_key"},
        )
        created = await client.post(
            API_KEYS,
            json=target,
            headers={"X-API-Key": original["key"]},
        )

        assert missing.status_code == 403
        assert missing.json() == {"detail": "Not authenticated"}
        assert invalid.status_code == 401
        assert invalid.json() == {"detail": "Invalid API key"}
        assert created.status_code == 201
        assert created.json()["tenant_id"] == original["tenant_id"]
        assert created.json()["key"] != original["key"]
        original_info = next(
            item
            for item in (await client.get(API_KEYS, headers=MASTER_HEADERS)).json()
            if item["prefix"] == original["prefix"]
        )
        assert original_info["last_used_at"] is None
        assert all(
            response.headers["Cache-Control"] == "no-store"
            for response in (missing, invalid, created)
        )

    async def test_master_can_issue_for_existing_workspace(self, client: AsyncClient):
        original = (await client.post(API_KEYS, json={})).json()
        created = await client.post(
            API_KEYS,
            json={"tenant_id": original["tenant_id"], "label": "master-issued"},
            headers=MASTER_HEADERS,
        )
        assert created.status_code == 201
        assert created.json()["tenant_id"] == original["tenant_id"]

    async def test_wrong_workspace_and_missing_workspace_are_indistinguishable(
        self, client: AsyncClient
    ):
        first = (await client.post(API_KEYS, json={"label": "first"})).json()
        second = (await client.post(API_KEYS, json={"label": "second"})).json()
        wrong_workspace = await client.post(
            API_KEYS,
            json={"tenant_id": second["tenant_id"]},
            headers={"X-API-Key": first["key"]},
        )
        absent_id = str(uuid.uuid4())
        missing_workspace = await client.post(
            API_KEYS,
            json={"tenant_id": absent_id},
            headers=MASTER_HEADERS,
        )
        for response in (wrong_workspace, missing_workspace):
            assert response.status_code == 404
            assert response.json() == {"detail": "Workspace not found"}
            assert response.headers["Cache-Control"] == "no-store"
            assert absent_id not in response.text

    async def test_revoked_key_cannot_issue_but_child_is_independent(
        self, client: AsyncClient
    ):
        original = (await client.post(API_KEYS, json={"label": "parent"})).json()
        child = await client.post(
            API_KEYS,
            json={"tenant_id": original["tenant_id"], "label": "child"},
            headers={"X-API-Key": original["key"]},
        )
        listed = (await client.get(API_KEYS, headers=MASTER_HEADERS)).json()
        parent = next(item for item in listed if item["prefix"] == original["prefix"])
        assert (
            await client.delete(f"{API_KEYS}/{parent['id']}", headers=MASTER_HEADERS)
        ).status_code == 204

        denied = await client.post(
            API_KEYS,
            json={"tenant_id": original["tenant_id"]},
            headers={"X-API-Key": original["key"]},
        )
        child_list = await client.get(
            API_KEYS, headers={"X-API-Key": child.json()["key"]}
        )
        assert denied.status_code == 401
        assert child_list.status_code == 200
        assert any(item["prefix"] == child.json()["prefix"] for item in child_list.json())

    async def test_public_and_existing_workspace_issuance_share_rate_limit(
        self, client: AsyncClient
    ):
        original = (await client.post(API_KEYS, json={})).json()
        for index in range(4):
            response = await client.post(
                API_KEYS,
                json={"tenant_id": original["tenant_id"], "label": f"child-{index}"},
                headers={"X-API-Key": original["key"]},
            )
            assert response.status_code == 201
        limited = await client.post(
            API_KEYS,
            json={"tenant_id": original["tenant_id"]},
            headers={"X-API-Key": original["key"]},
        )
        assert limited.status_code == 429
        assert limited.headers["Cache-Control"] == "no-store"


class TestExistingWorkspaceIssuanceConcurrency:
    async def test_issuance_lock_serializes_revoke_after_child_commit(
        self, engine, setup_database
    ):
        from app.core.security import authenticate_api_key
        from app.crud.crud_api_key import create_api_key, get_api_key, revoke_api_key

        sessions = async_sessionmaker(engine, expire_on_commit=False)
        tenant_id = None
        try:
            async with sessions() as seed:
                issuer, raw_key = await create_api_key(seed, label="race-issuer")
                tenant_id, issuer_id = issuer.tenant_id, issuer.id
                await seed.commit()

            async with sessions() as issuance, sessions() as revocation:
                await authenticate_api_key(
                    raw_key,
                    issuance,
                    touch_last_used=False,
                    lock_generated_key_for_share=True,
                )
                revocation_pid = await revocation.scalar(text("SELECT pg_backend_pid()"))

                async def revoke():
                    current = await get_api_key(revocation, issuer_id)
                    assert current is not None
                    await revoke_api_key(revocation, current)
                    await revocation.commit()

                revoke_task = asyncio.create_task(revoke())
                try:
                    await wait_for_database_lock(sessions, revocation_pid)
                    child, _ = await create_api_key(
                        issuance, label="race-child", tenant_id=tenant_id
                    )
                    child_id = child.id
                    await issuance.commit()
                    await asyncio.wait_for(revoke_task, timeout=2)
                finally:
                    if not revoke_task.done():
                        await issuance.rollback()
                        await asyncio.wait_for(revoke_task, timeout=2)

            async with sessions() as verify:
                issuer_active = await verify.scalar(
                    select(ApiKey.is_active).where(ApiKey.id == issuer_id)
                )
                child_active = await verify.scalar(
                    select(ApiKey.is_active).where(ApiKey.id == child_id)
                )
                assert issuer_active is False
                assert child_active is True
        finally:
            if tenant_id is not None:
                async with sessions() as cleanup:
                    await cleanup.execute(delete(ApiKey).where(ApiKey.tenant_id == tenant_id))
                    await cleanup.commit()

    async def test_revoke_lock_makes_waiting_issuance_fail_closed(
        self, engine, setup_database
    ):
        from app.core.security import authenticate_api_key
        from app.crud.crud_api_key import create_api_key, get_api_key, revoke_api_key

        sessions = async_sessionmaker(engine, expire_on_commit=False)
        tenant_id = None
        try:
            async with sessions() as seed:
                issuer, raw_key = await create_api_key(seed, label="race-issuer")
                tenant_id, issuer_id = issuer.tenant_id, issuer.id
                await seed.commit()

            async with sessions() as revocation, sessions() as issuance:
                current = await get_api_key(revocation, issuer_id)
                assert current is not None
                await revoke_api_key(revocation, current)
                issuance_pid = await issuance.scalar(text("SELECT pg_backend_pid()"))

                auth_task = asyncio.create_task(
                    authenticate_api_key(
                        raw_key,
                        issuance,
                        touch_last_used=False,
                        lock_generated_key_for_share=True,
                    )
                )
                try:
                    await wait_for_database_lock(sessions, issuance_pid)
                    await revocation.commit()
                    with pytest.raises(HTTPException) as denied:
                        await asyncio.wait_for(auth_task, timeout=2)
                    assert denied.value.status_code == 401
                finally:
                    if not auth_task.done():
                        await revocation.rollback()
                        await asyncio.wait_for(auth_task, timeout=2)
        finally:
            if tenant_id is not None:
                async with sessions() as cleanup:
                    await cleanup.execute(delete(ApiKey).where(ApiKey.tenant_id == tenant_id))
                    await cleanup.commit()

    async def test_two_issuers_share_lock_without_touch_or_deadlock(
        self, engine, setup_database
    ):
        from app.core.security import authenticate_api_key
        from app.crud.crud_api_key import create_api_key

        sessions = async_sessionmaker(engine, expire_on_commit=False)
        tenant_id = None
        try:
            async with sessions() as seed:
                issuer, raw_key = await create_api_key(seed, label="shared-issuer")
                tenant_id, issuer_id = issuer.tenant_id, issuer.id
                await seed.commit()

            ready = 0
            ready_lock = asyncio.Lock()
            both_ready = asyncio.Event()

            async def issue(label: str):
                nonlocal ready
                async with sessions() as session:
                    await authenticate_api_key(
                        raw_key,
                        session,
                        touch_last_used=False,
                        lock_generated_key_for_share=True,
                    )
                    async with ready_lock:
                        ready += 1
                        if ready == 2:
                            both_ready.set()
                    await asyncio.wait_for(both_ready.wait(), timeout=2)
                    child, _ = await create_api_key(
                        session, label=label, tenant_id=tenant_id
                    )
                    await session.commit()
                    return child.id

            child_ids = await asyncio.wait_for(
                asyncio.gather(issue("parallel-child-a"), issue("parallel-child-b")),
                timeout=3,
            )
            assert len(set(child_ids)) == 2
            async with sessions() as verify:
                issuer_last_used = await verify.scalar(
                    select(ApiKey.last_used_at).where(ApiKey.id == issuer_id)
                )
                children = (
                    await verify.scalars(
                        select(ApiKey).where(ApiKey.id.in_(child_ids))
                    )
                ).all()
                assert issuer_last_used is None
                assert len(children) == 2
                assert all(child.is_active for child in children)
        finally:
            if tenant_id is not None:
                async with sessions() as cleanup:
                    await cleanup.execute(delete(ApiKey).where(ApiKey.tenant_id == tenant_id))
                    await cleanup.commit()


# ── Generated key can authenticate ───────────────────────────────

class TestKeyAuthentication:
    async def test_generated_key_authenticates(self, client: AsyncClient, db_session):
        """A generated key should be accepted by auth-protected endpoints."""
        from app.crud.crud_api_key import create_api_key

        api_key_model, raw_key = await create_api_key(db_session, label="auth-test")

        # Make a request with the generated key (bypass the override)
        from app.main import app
        from app.api.deps import get_db_session

        # We need to use the db_session override but NOT the api_key override
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db
        # Remove api_key override so real validation happens
        from app.core.security import get_api_key
        if get_api_key in app.dependency_overrides:
            del app.dependency_overrides[get_api_key]

        from httpx import AsyncClient as AC, ASGITransport
        transport = ASGITransport(app=app)
        async with AC(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/hypotheses",
                headers={"X-API-Key": raw_key},
            )
            assert resp.status_code == 200

    async def test_invalid_key_rejected(self, client: AsyncClient, db_session):
        """A random key that wasn't generated should be rejected."""
        from app.main import app
        from app.api.deps import get_db_session

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db
        from app.core.security import get_api_key
        if get_api_key in app.dependency_overrides:
            del app.dependency_overrides[get_api_key]

        from httpx import AsyncClient as AC, ASGITransport
        transport = ASGITransport(app=app)
        async with AC(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/hypotheses",
                headers={"X-API-Key": "he_this_is_not_a_valid_key"},
            )
            assert resp.status_code == 401


# ── GET /keys (admin — master key only) ──────────────────────────

class TestListKeys:
    async def test_list_keys(self, client: AsyncClient):
        # Generate a couple of keys first
        await client.post(API_KEYS, json={"label": "key-1"})
        await client.post(API_KEYS, json={"label": "key-2"})

        resp = await client.get(API_KEYS, headers=MASTER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        # Should NOT contain full key material
        for k in data:
            assert "key" not in k or len(k.get("key", "")) <= 12
            assert "prefix" in k
            assert "is_active" in k

    async def test_list_keys_shows_prefix_not_key(self, client: AsyncClient):
        resp_gen = await client.post(API_KEYS, json={"label": "prefix-test"})
        generated = resp_gen.json()

        resp = await client.get(API_KEYS, headers=MASTER_HEADERS)
        data = resp.json()
        prefixes = [k["prefix"] for k in data]
        assert generated["prefix"] in prefixes
        # Full key should never appear in list response
        keys_in_list = [k.get("key", "") for k in data]
        assert generated["key"] not in keys_in_list

    async def test_list_keys_rejects_missing_and_invalid_keys(self, client: AsyncClient):
        missing = await client.get(API_KEYS)
        invalid = await client.get(API_KEYS, headers={"X-API-Key": "not-a-real-key"})
        assert missing.status_code == 403
        assert invalid.status_code == 401


# ── DELETE /keys/{id} (admin — master key only) ──────────────────

class TestRevokeKey:
    async def test_revoke_key(self, client: AsyncClient):
        # Generate a key
        resp_gen = await client.post(API_KEYS, json={"label": "revoke-me"})
        assert resp_gen.status_code == 201

        # List to find the key's ID
        resp_list = await client.get(API_KEYS, headers=MASTER_HEADERS)
        keys = resp_list.json()
        target = next(k for k in keys if k["label"] == "revoke-me")

        # Revoke it
        resp = await client.delete(f"{API_KEYS}/{target['id']}", headers=MASTER_HEADERS)
        assert resp.status_code == 204

    async def test_revoke_nonexistent_404(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.delete(f"{API_KEYS}/{fake_id}", headers=MASTER_HEADERS)
        assert resp.status_code == 404

    async def test_revoke_key_rejects_missing_and_wrong_master_key(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        missing = await client.delete(f"{API_KEYS}/{fake_id}")
        wrong = await client.delete(f"{API_KEYS}/{fake_id}", headers={"X-API-Key": "not-the-master-key"})
        assert missing.status_code == 403
        assert wrong.status_code == 403

    async def test_revoked_key_excluded_from_default_list(self, client: AsyncClient):
        # Generate and revoke
        resp_gen = await client.post(API_KEYS, json={"label": "will-revoke"})
        resp_list = await client.get(API_KEYS, headers=MASTER_HEADERS)
        target = next(k for k in resp_list.json() if k["label"] == "will-revoke")
        await client.delete(f"{API_KEYS}/{target['id']}", headers=MASTER_HEADERS)

        # Default list should not include revoked
        resp = await client.get(API_KEYS, headers=MASTER_HEADERS)
        labels = [k["label"] for k in resp.json()]
        assert "will-revoke" not in labels

    async def test_revoked_key_included_with_flag(self, client: AsyncClient):
        # Generate and revoke
        resp_gen = await client.post(API_KEYS, json={"label": "include-revoked"})
        resp_list = await client.get(API_KEYS, headers=MASTER_HEADERS)
        target = next(k for k in resp_list.json() if k["label"] == "include-revoked")
        await client.delete(f"{API_KEYS}/{target['id']}", headers=MASTER_HEADERS)

        # With include_revoked=true, should appear
        resp = await client.get(API_KEYS, params={"include_revoked": "true"}, headers=MASTER_HEADERS)
        found = [k for k in resp.json() if k["label"] == "include-revoked"]
        assert len(found) == 1
        assert found[0]["is_active"] is False
