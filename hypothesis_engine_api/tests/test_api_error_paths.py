"""Error path tests — auth failures, malformed input, immutability, business rule violations.

These cover gaps not handled by the happy-path integration tests.
"""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.api.deps import get_db_session

API = "/api/v1"


# ── Helpers ───────────────────────────────────────────────────────


async def create_hypothesis(client: AsyncClient, **overrides) -> dict:
    payload = {"statement": "Error-path test hypothesis", "created_by": "test-agent"}
    payload.update(overrides)
    resp = await client.post(f"{API}/hypotheses", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def move_to(client: AsyncClient, hid: str, status: str) -> dict:
    resp = await client.patch(
        f"{API}/hypotheses/{hid}", json={"status": status, "created_by": "test"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Authentication ────────────────────────────────────────────────


class TestAuthFailures:
    """Tests with a client that does NOT override auth."""

    @pytest.fixture
    async def unauthed_client(self, db_session: AsyncSession):
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db_session] = override_get_db
        # No auth override — real auth dependency runs
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        app.dependency_overrides.clear()

    async def test_missing_api_key_returns_403(self, unauthed_client: AsyncClient):
        """FastAPI's APIKeyHeader with auto_error=True returns 403 when header is missing."""
        resp = await unauthed_client.get(f"{API}/hypotheses")
        assert resp.status_code == 403

    async def test_invalid_api_key_returns_401(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.get(
            f"{API}/hypotheses",
            headers={"X-API-Key": "totally-invalid-key"},
        )
        assert resp.status_code == 401
        assert "Invalid API key" in resp.json()["detail"]

    async def test_invalid_key_on_post(self, unauthed_client: AsyncClient):
        resp = await unauthed_client.post(
            f"{API}/hypotheses",
            json={"statement": "test", "created_by": "test"},
            headers={"X-API-Key": "bad-key"},
        )
        assert resp.status_code == 401

    async def test_public_endpoints_need_no_auth(self, unauthed_client: AsyncClient):
        """Health and SKILL.md endpoints should work without auth."""
        resp = await unauthed_client.get(f"{API}/health")
        assert resp.status_code == 200
        resp = await unauthed_client.get(f"{API}/skill/version")
        assert resp.status_code == 200


# ── 404 Coverage ──────────────────────────────────────────────────


class TestNotFoundPaths:

    async def test_get_nonexistent_hypothesis(self, client: AsyncClient):
        resp = await client.get(f"{API}/hypotheses/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_patch_nonexistent_hypothesis(self, client: AsyncClient):
        resp = await client.patch(
            f"{API}/hypotheses/{uuid.uuid4()}",
            json={"confidence": 0.5, "created_by": "test"},
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent_hypothesis(self, client: AsyncClient):
        resp = await client.delete(f"{API}/hypotheses/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_evidence_on_nonexistent_hypothesis(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/hypotheses/{uuid.uuid4()}/evidence",
            json={"content": "test", "evidence_type": "supporting", "created_by": "test"},
        )
        assert resp.status_code == 404

    async def test_list_evidence_on_nonexistent(self, client: AsyncClient):
        resp = await client.get(f"{API}/hypotheses/{uuid.uuid4()}/evidence")
        assert resp.status_code == 404

    async def test_timeline_of_nonexistent(self, client: AsyncClient):
        resp = await client.get(f"{API}/hypotheses/{uuid.uuid4()}/timeline")
        assert resp.status_code == 404

    async def test_lineage_of_nonexistent(self, client: AsyncClient):
        resp = await client.get(f"{API}/hypotheses/{uuid.uuid4()}/lineage")
        assert resp.status_code == 404

    async def test_revise_nonexistent(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/hypotheses/{uuid.uuid4()}/revise",
            json={"statement": "rev", "created_by": "test", "rationale": "why"},
        )
        assert resp.status_code == 404

    async def test_relationships_of_nonexistent(self, client: AsyncClient):
        resp = await client.get(f"{API}/hypotheses/{uuid.uuid4()}/relationships")
        assert resp.status_code == 404

    async def test_network_of_nonexistent(self, client: AsyncClient):
        resp = await client.get(f"{API}/hypotheses/{uuid.uuid4()}/network")
        assert resp.status_code == 404

    async def test_create_relationship_to_nonexistent_target(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.post(
            f"{API}/hypotheses/{h['id']}/relationships",
            json={
                "target_hypothesis_id": str(uuid.uuid4()),
                "relationship_type": "competes_with",
                "created_by": "test",
            },
        )
        assert resp.status_code == 404

    async def test_get_nonexistent_insight(self, client: AsyncClient):
        resp = await client.get(f"{API}/insights/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_patch_nonexistent_insight(self, client: AsyncClient):
        resp = await client.patch(
            f"{API}/insights/{uuid.uuid4()}",
            json={"content": "new", "updated_by": "test"},
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent_insight(self, client: AsyncClient):
        resp = await client.delete(f"{API}/insights/{uuid.uuid4()}")
        assert resp.status_code == 404


# ── Malformed Input ───────────────────────────────────────────────


class TestMalformedInput:

    async def test_invalid_uuid_in_path(self, client: AsyncClient):
        resp = await client.get(f"{API}/hypotheses/not-a-uuid")
        assert resp.status_code == 422

    async def test_missing_required_statement(self, client: AsyncClient):
        resp = await client.post(f"{API}/hypotheses", json={"created_by": "test"})
        assert resp.status_code == 422

    async def test_missing_required_created_by(self, client: AsyncClient):
        resp = await client.post(f"{API}/hypotheses", json={"statement": "test"})
        assert resp.status_code == 422

    async def test_empty_body(self, client: AsyncClient):
        resp = await client.post(f"{API}/hypotheses", json={})
        assert resp.status_code == 422

    async def test_confidence_above_one(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/hypotheses",
            json={"statement": "test", "created_by": "test", "confidence": 1.5},
        )
        assert resp.status_code == 422

    async def test_confidence_below_zero(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/hypotheses",
            json={"statement": "test", "created_by": "test", "confidence": -0.1},
        )
        assert resp.status_code == 422

    async def test_invalid_status_on_create(self, client: AsyncClient):
        """Can only create in draft or active status."""
        resp = await client.post(
            f"{API}/hypotheses",
            json={"statement": "test", "created_by": "test", "status": "supported"},
        )
        assert resp.status_code == 422

    async def test_invalid_status_filter_value(self, client: AsyncClient):
        resp = await client.get(f"{API}/hypotheses?status=bogus")
        assert resp.status_code == 422

    async def test_created_by_xss_injection(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/hypotheses",
            json={"statement": "test", "created_by": "<script>alert(1)</script>"},
        )
        assert resp.status_code == 422

    async def test_invalid_evidence_type(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.post(
            f"{API}/hypotheses/{h['id']}/evidence",
            json={"content": "test", "evidence_type": "invalid_type", "created_by": "test"},
        )
        assert resp.status_code == 422

    async def test_invalid_insight_type(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/insights",
            json={
                "channel": "test",
                "insight_type": "bogus",
                "content": "test",
                "created_by": "test",
            },
        )
        assert resp.status_code == 422

    async def test_empty_evidence_content(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.post(
            f"{API}/hypotheses/{h['id']}/evidence",
            json={"content": "", "evidence_type": "supporting", "created_by": "test"},
        )
        assert resp.status_code == 422

    async def test_empty_insight_content(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/insights",
            json={"channel": "test", "insight_type": "calibration", "content": "", "created_by": "test"},
        )
        assert resp.status_code == 422

    async def test_negative_pagination_offset(self, client: AsyncClient):
        resp = await client.get(f"{API}/hypotheses?offset=-1")
        assert resp.status_code == 422

    async def test_zero_pagination_limit(self, client: AsyncClient):
        resp = await client.get(f"{API}/hypotheses?limit=0")
        assert resp.status_code == 422

    async def test_excessive_pagination_limit(self, client: AsyncClient):
        resp = await client.get(f"{API}/hypotheses?limit=999")
        assert resp.status_code == 422


# ── Business Rule Violations ──────────────────────────────────────


class TestBusinessRuleViolations:

    async def test_active_cannot_skip_to_supported(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        resp = await client.patch(
            f"{API}/hypotheses/{h['id']}",
            json={"status": "supported", "created_by": "test"},
        )
        assert resp.status_code == 409

    async def test_active_cannot_skip_to_refuted(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        resp = await client.patch(
            f"{API}/hypotheses/{h['id']}",
            json={"status": "refuted", "created_by": "test"},
        )
        assert resp.status_code == 409

    async def test_draft_cannot_go_to_supported(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.patch(
            f"{API}/hypotheses/{h['id']}",
            json={"status": "supported", "created_by": "test"},
        )
        assert resp.status_code == 409

    async def test_add_evidence_to_archived(self, client: AsyncClient):
        h = await create_hypothesis(client)
        await client.delete(f"{API}/hypotheses/{h['id']}")
        resp = await client.post(
            f"{API}/hypotheses/{h['id']}/evidence",
            json={"content": "test", "evidence_type": "supporting", "created_by": "test"},
        )
        assert resp.status_code == 409

    async def test_modify_archived_without_unarchiving(self, client: AsyncClient):
        h = await create_hypothesis(client)
        await client.delete(f"{API}/hypotheses/{h['id']}")
        resp = await client.patch(
            f"{API}/hypotheses/{h['id']}",
            json={"confidence": 0.5, "created_by": "test"},
        )
        assert resp.status_code == 409

    async def test_self_referencing_relationship(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.post(
            f"{API}/hypotheses/{h['id']}/relationships",
            json={
                "target_hypothesis_id": h["id"],
                "relationship_type": "competes_with",
                "created_by": "test",
            },
        )
        assert resp.status_code == 400

    async def test_duplicate_relationship(self, client: AsyncClient):
        h1 = await create_hypothesis(client)
        h2 = await create_hypothesis(client, statement="Other")
        payload = {
            "target_hypothesis_id": h2["id"],
            "relationship_type": "competes_with",
            "created_by": "test",
        }
        resp1 = await client.post(f"{API}/hypotheses/{h1['id']}/relationships", json=payload)
        assert resp1.status_code == 201
        resp2 = await client.post(f"{API}/hypotheses/{h1['id']}/relationships", json=payload)
        assert resp2.status_code == 409

    async def test_symmetric_duplicate_relationship(self, client: AsyncClient):
        """competes_with is symmetric: H1→H2 blocks H2→H1."""
        h1 = await create_hypothesis(client)
        h2 = await create_hypothesis(client, statement="Other")
        resp1 = await client.post(
            f"{API}/hypotheses/{h1['id']}/relationships",
            json={
                "target_hypothesis_id": h2["id"],
                "relationship_type": "competes_with",
                "created_by": "test",
            },
        )
        assert resp1.status_code == 201
        # Reverse direction should be blocked
        resp2 = await client.post(
            f"{API}/hypotheses/{h2['id']}/relationships",
            json={
                "target_hypothesis_id": h1["id"],
                "relationship_type": "competes_with",
                "created_by": "test",
            },
        )
        assert resp2.status_code == 409

    async def test_revise_draft_fails(self, client: AsyncClient):
        """Cannot revise a draft hypothesis."""
        h = await create_hypothesis(client)
        resp = await client.post(
            f"{API}/hypotheses/{h['id']}/revise",
            json={"statement": "rev", "created_by": "test", "rationale": "why"},
        )
        assert resp.status_code == 409

    async def test_revise_active_fails(self, client: AsyncClient):
        """Cannot revise an active hypothesis (only terminal states can be revised)."""
        h = await create_hypothesis(client, status="active")
        resp = await client.post(
            f"{API}/hypotheses/{h['id']}/revise",
            json={"statement": "rev", "created_by": "test", "rationale": "why"},
        )
        assert resp.status_code == 409


# ── Immutability Enforcement ──────────────────────────────────────


class TestImmutability:

    async def test_evidence_cannot_be_patched(self, client: AsyncClient):
        """No PATCH endpoint exists for evidence."""
        h = await create_hypothesis(client)
        resp = await client.post(
            f"{API}/hypotheses/{h['id']}/evidence",
            json={"content": "original", "evidence_type": "supporting", "created_by": "test"},
        )
        assert resp.status_code == 201
        eid = resp.json()["evidence"]["id"]
        resp = await client.patch(
            f"{API}/hypotheses/{h['id']}/evidence/{eid}",
            json={"content": "modified"},
        )
        # No route exists — should be 404 or 405
        assert resp.status_code in (404, 405)

    async def test_evidence_cannot_be_deleted(self, client: AsyncClient):
        """No DELETE endpoint exists for evidence."""
        h = await create_hypothesis(client)
        resp = await client.post(
            f"{API}/hypotheses/{h['id']}/evidence",
            json={"content": "original", "evidence_type": "supporting", "created_by": "test"},
        )
        assert resp.status_code == 201
        eid = resp.json()["evidence"]["id"]
        resp = await client.delete(f"{API}/hypotheses/{h['id']}/evidence/{eid}")
        assert resp.status_code in (404, 405)

    async def test_timeline_events_cannot_be_deleted(self, client: AsyncClient):
        """No DELETE endpoint exists for timeline events."""
        h = await create_hypothesis(client)
        resp = await client.get(f"{API}/hypotheses/{h['id']}/timeline")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 1
        eid = events[0]["id"]
        resp = await client.delete(f"{API}/hypotheses/{h['id']}/timeline/{eid}")
        assert resp.status_code in (404, 405)

    async def test_timeline_events_cannot_be_patched(self, client: AsyncClient):
        """No PATCH endpoint exists for timeline events."""
        h = await create_hypothesis(client)
        resp = await client.get(f"{API}/hypotheses/{h['id']}/timeline")
        events = resp.json()
        eid = events[0]["id"]
        resp = await client.patch(
            f"{API}/hypotheses/{h['id']}/timeline/{eid}",
            json={"data": {"modified": True}},
        )
        assert resp.status_code in (404, 405)


# ── Transaction Atomicity ─────────────────────────────────────────


class TestTransactionAtomicity:

    async def test_status_change_emits_event_atomically(self, client: AsyncClient):
        """Status change + event emission should be atomic — both succeed or neither does."""
        h = await create_hypothesis(client, status="active")
        resp = await client.patch(
            f"{API}/hypotheses/{h['id']}",
            json={"status": "testing", "created_by": "test"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "testing"

        # Verify the event was recorded
        resp = await client.get(f"{API}/hypotheses/{h['id']}/timeline")
        events = resp.json()
        event_types = [e["event_type"] for e in events]
        assert "status_changed" in event_types

    async def test_evidence_with_confidence_update_atomic(self, client: AsyncClient):
        """Adding evidence + updating confidence should be atomic."""
        h = await create_hypothesis(client, status="active", confidence=0.5)
        resp = await client.post(
            f"{API}/hypotheses/{h['id']}/evidence",
            json={
                "content": "Strong evidence found",
                "evidence_type": "supporting",
                "created_by": "test",
                "confidence": 0.8,
            },
        )
        assert resp.status_code == 201
        # Both evidence and confidence should reflect
        assert resp.json()["hypothesis"]["confidence"] == 0.8
        assert resp.json()["evidence"]["content"] == "Strong evidence found"

    async def test_revise_creates_both_hypotheses_atomically(self, client: AsyncClient):
        """Revision should create new hypothesis and mark old as revised atomically."""
        h = await create_hypothesis(client, status="active")
        await move_to(client, h["id"], "testing")
        await client.patch(
            f"{API}/hypotheses/{h['id']}",
            json={"status": "supported", "created_by": "test", "outcome": {"result": "Synthetic test conclusion"}},
        )

        resp = await client.post(
            f"{API}/hypotheses/{h['id']}/revise",
            json={
                "statement": "Revised version",
                "created_by": "test",
                "rationale": "New evidence emerged",
            },
        )
        assert resp.status_code == 201
        new_h = resp.json()
        assert new_h["parent_id"] == h["id"]

        # Old hypothesis should be marked as revised
        resp = await client.get(f"{API}/hypotheses/{h['id']}")
        assert resp.json()["status"] == "revised"
