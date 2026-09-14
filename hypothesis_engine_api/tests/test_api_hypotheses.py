"""API integration tests for hypothesis endpoints."""

import pytest
from httpx import AsyncClient

API = "/api/v1/hypotheses"


# ── Helpers ───────────────────────────────────────────────────────

async def create_hypothesis(client: AsyncClient, **overrides) -> dict:
    payload = {
        "statement": "Default test hypothesis",
        "created_by": "test-agent",
    }
    payload.update(overrides)
    resp = await client.post(API, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def move_to_testing(client: AsyncClient, hypothesis_id: str) -> dict:
    """Helper: active → testing."""
    resp = await client.patch(f"{API}/{hypothesis_id}", json={"status": "testing"})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Create ────────────────────────────────────────────────────────

class TestCreateHypothesis:
    async def test_create_minimal(self, client: AsyncClient):
        data = await create_hypothesis(client)
        assert data["statement"] == "Default test hypothesis"
        assert data["status"] == "draft"
        assert data["confidence"] is None
        assert data["tags"] == []
        assert data["created_by"] == "test-agent"
        assert data["is_archived"] is False
        assert data["parent_id"] is None
        assert data["falsification_criteria"] is None
        assert data["deadline"] is None
        assert data["metadata"] is None
        assert data["null_hypothesis"] is None
        assert data["experimental_design"] is None
        assert data["significance_level"] is None
        assert data["outcome"] is None
        assert data["evidence_counts"] == {"supporting": 0, "contradicting": 0, "neutral": 0}

    async def test_create_full(self, client: AsyncClient):
        design = {"independent_variable": "Time", "dependent_variable": "Price", "control": "S&P 500"}
        data = await create_hypothesis(
            client,
            statement="DB pool is exhausted",
            context="After deploy to prod",
            falsification_criteria="If connections are returned normally, this is wrong",
            status="active",
            confidence=0.7,
            tags=["debugging", "database"],
            created_by="claude-code",
            deadline="2026-05-19T00:00:00Z",
            metadata={"component": "db-pool", "deploy_id": "v2.3.1"},
            null_hypothesis="DB pool is NOT exhausted",
            experimental_design=design,
            significance_level=0.05,
            outcome={"result": "pending"},
        )
        assert data["status"] == "active"
        assert data["confidence"] == 0.7
        assert data["tags"] == ["debugging", "database"]
        assert data["context"] == "After deploy to prod"
        assert data["falsification_criteria"] == "If connections are returned normally, this is wrong"
        assert data["deadline"] is not None
        assert "2026-05-19" in data["deadline"]
        assert data["metadata"] == {"component": "db-pool", "deploy_id": "v2.3.1"}
        assert data["null_hypothesis"] == "DB pool is NOT exhausted"
        assert data["experimental_design"] == design
        assert data["significance_level"] == 0.05
        assert data["outcome"] == {"result": "pending"}

    async def test_create_tags_normalized(self, client: AsyncClient):
        data = await create_hypothesis(client, tags=["  FOO ", "Bar", "baz"])
        assert data["tags"] == ["foo", "bar", "baz"]

    async def test_create_invalid_missing_statement(self, client: AsyncClient):
        resp = await client.post(API, json={"created_by": "x"})
        assert resp.status_code == 422

    async def test_create_invalid_confidence(self, client: AsyncClient):
        resp = await client.post(API, json={"statement": "T", "created_by": "x", "confidence": 1.5})
        assert resp.status_code == 422


# ── Get ───────────────────────────────────────────────────────────

class TestGetHypothesis:
    async def test_get_by_id(self, client: AsyncClient):
        created = await create_hypothesis(client)
        resp = await client.get(f"{API}/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    async def test_get_includes_falsification_criteria(self, client: AsyncClient):
        created = await create_hypothesis(
            client,
            falsification_criteria="If X then this is wrong",
        )
        resp = await client.get(f"{API}/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["falsification_criteria"] == "If X then this is wrong"

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API}/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ── List ──────────────────────────────────────────────────────────

class TestListHypotheses:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get(API)
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] >= 0

    async def test_list_returns_created(self, client: AsyncClient):
        await create_hypothesis(client, statement="Unique search target")
        resp = await client.get(API, params={"search": "Unique search target"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(h["statement"] == "Unique search target" for h in items)

    async def test_list_filter_by_status(self, client: AsyncClient):
        await create_hypothesis(client, status="active")
        resp = await client.get(API, params={"status": "active"})
        assert resp.status_code == 200
        for h in resp.json()["items"]:
            assert h["status"] == "active"

    async def test_list_filter_by_tags(self, client: AsyncClient):
        await create_hypothesis(client, tags=["unique-tag-xyz"])
        resp = await client.get(API, params={"tags": "unique-tag-xyz"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        for h in items:
            assert "unique-tag-xyz" in h["tags"]

    async def test_list_filter_by_created_by(self, client: AsyncClient):
        await create_hypothesis(client, created_by="specific-agent-789")
        resp = await client.get(API, params={"created_by": "specific-agent-789"})
        assert resp.status_code == 200
        for h in resp.json()["items"]:
            assert h["created_by"] == "specific-agent-789"

    async def test_list_confidence_range(self, client: AsyncClient):
        await create_hypothesis(client, confidence=0.5, status="active")
        await create_hypothesis(client, confidence=0.9, status="active")
        resp = await client.get(API, params={"confidence_min": 0.4, "confidence_max": 0.6})
        assert resp.status_code == 200
        for h in resp.json()["items"]:
            assert 0.4 <= h["confidence"] <= 0.6

    async def test_list_pagination(self, client: AsyncClient):
        for i in range(3):
            await create_hypothesis(client, statement=f"Pagination test {i}")
        resp = await client.get(API, params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) <= 2

    async def test_list_filter_by_deadline(self, client: AsyncClient):
        await create_hypothesis(client, deadline="2026-03-01T00:00:00Z", statement="Due in March")
        await create_hypothesis(client, deadline="2026-06-01T00:00:00Z", statement="Due in June")
        # Only hypotheses with deadline before April
        resp = await client.get(API, params={"deadline_before": "2026-04-01T00:00:00Z"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        for h in items:
            assert h["deadline"] is not None
            assert h["deadline"] < "2026-04-01"

    async def test_list_excludes_archived_by_default(self, client: AsyncClient):
        created = await create_hypothesis(client, statement="Will be archived")
        await client.delete(f"{API}/{created['id']}")
        resp = await client.get(API, params={"search": "Will be archived"})
        items = resp.json()["items"]
        assert not any(h["statement"] == "Will be archived" for h in items)

    async def test_list_includes_archived_when_requested(self, client: AsyncClient):
        created = await create_hypothesis(client, statement="Archived visible")
        await client.delete(f"{API}/{created['id']}")
        resp = await client.get(API, params={"search": "Archived visible", "is_archived": "true"})
        items = resp.json()["items"]
        assert any(h["statement"] == "Archived visible" for h in items)


# ── Update ────────────────────────────────────────────────────────

class TestUpdateHypothesis:
    async def test_update_statement(self, client: AsyncClient):
        created = await create_hypothesis(client)
        resp = await client.patch(f"{API}/{created['id']}", json={"statement": "Updated statement"})
        assert resp.status_code == 200
        assert resp.json()["statement"] == "Updated statement"

    async def test_update_confidence(self, client: AsyncClient):
        created = await create_hypothesis(client)
        resp = await client.patch(f"{API}/{created['id']}", json={"confidence": 0.8})
        assert resp.status_code == 200
        assert resp.json()["confidence"] == 0.8

    async def test_update_tags(self, client: AsyncClient):
        created = await create_hypothesis(client)
        resp = await client.patch(f"{API}/{created['id']}", json={"tags": ["new-tag"]})
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["new-tag"]

    async def test_update_falsification_criteria(self, client: AsyncClient):
        created = await create_hypothesis(client)
        resp = await client.patch(
            f"{API}/{created['id']}",
            json={"falsification_criteria": "If X then this is disproved"},
        )
        assert resp.status_code == 200
        assert resp.json()["falsification_criteria"] == "If X then this is disproved"

    async def test_update_deadline(self, client: AsyncClient):
        created = await create_hypothesis(client)
        resp = await client.patch(
            f"{API}/{created['id']}",
            json={"deadline": "2026-06-01T00:00:00Z"},
        )
        assert resp.status_code == 200
        assert "2026-06-01" in resp.json()["deadline"]

    async def test_update_metadata(self, client: AsyncClient):
        created = await create_hypothesis(client)
        resp = await client.patch(
            f"{API}/{created['id']}",
            json={"metadata": {"ticker": "ACME", "target_price": 5.0}},
        )
        assert resp.status_code == 200
        assert resp.json()["metadata"] == {"ticker": "ACME", "target_price": 5.0}

    async def test_update_null_hypothesis(self, client: AsyncClient):
        created = await create_hypothesis(client)
        resp = await client.patch(
            f"{API}/{created['id']}",
            json={"null_hypothesis": "The system is NOT experiencing issues"},
        )
        assert resp.status_code == 200
        assert resp.json()["null_hypothesis"] == "The system is NOT experiencing issues"

    async def test_update_experimental_design(self, client: AsyncClient):
        created = await create_hypothesis(client)
        design = {"independent_variable": "Time", "control": "Baseline"}
        resp = await client.patch(
            f"{API}/{created['id']}",
            json={"experimental_design": design},
        )
        assert resp.status_code == 200
        assert resp.json()["experimental_design"] == design

    async def test_update_outcome(self, client: AsyncClient):
        created = await create_hypothesis(client, status="active")
        await move_to_testing(client, created["id"])
        outcome = {"result": "reject_h0", "actual_value": 5.20, "narrative": "Target reached"}
        resp = await client.patch(
            f"{API}/{created['id']}",
            json={"status": "supported", "outcome": outcome},
        )
        assert resp.status_code == 200
        assert resp.json()["outcome"] == outcome

    async def test_valid_status_transition(self, client: AsyncClient):
        created = await create_hypothesis(client, status="draft")
        resp = await client.patch(f"{API}/{created['id']}", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    async def test_invalid_status_transition(self, client: AsyncClient):
        created = await create_hypothesis(client, status="draft")
        resp = await client.patch(f"{API}/{created['id']}", json={"status": "supported", "outcome": {"result": "Synthetic test conclusion"}})
        assert resp.status_code == 409

    async def test_update_not_found(self, client: AsyncClient):
        resp = await client.patch(
            f"{API}/00000000-0000-0000-0000-000000000000",
            json={"statement": "X"},
        )
        assert resp.status_code == 404


# ── Status Transitions ────────────────────────────────────────────

class TestStatusTransitions:
    async def test_draft_to_active(self, client: AsyncClient):
        h = await create_hypothesis(client, status="draft")
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    async def test_active_to_testing(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "testing"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "testing"

    async def test_cannot_skip_testing_to_supported(self, client: AsyncClient):
        """active → supported is not allowed — must go through testing."""
        h = await create_hypothesis(client, status="active")
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "supported", "outcome": {"result": "Synthetic test conclusion"}})
        assert resp.status_code == 409

    async def test_cannot_skip_testing_to_refuted(self, client: AsyncClient):
        """active → refuted is not allowed — must go through testing."""
        h = await create_hypothesis(client, status="active")
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "refuted", "outcome": {"result": "Synthetic test conclusion"}})
        assert resp.status_code == 409

    async def test_cannot_skip_testing_to_inconclusive(self, client: AsyncClient):
        """active → inconclusive is not allowed — must go through testing."""
        h = await create_hypothesis(client, status="active")
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "inconclusive", "outcome": {"result": "Synthetic test conclusion"}})
        assert resp.status_code == 409

    async def test_testing_to_supported(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        await move_to_testing(client, h["id"])
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "supported", "outcome": {"result": "Synthetic test conclusion"}})
        assert resp.status_code == 200
        assert resp.json()["status"] == "supported"

    async def test_testing_to_refuted(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        await move_to_testing(client, h["id"])
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "refuted", "outcome": {"result": "Synthetic test conclusion"}})
        assert resp.status_code == 200
        assert resp.json()["status"] == "refuted"

    async def test_testing_to_inconclusive(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        await move_to_testing(client, h["id"])
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "inconclusive", "outcome": {"result": "Synthetic test conclusion"}})
        assert resp.status_code == 200
        assert resp.json()["status"] == "inconclusive"

    async def test_inconclusive_back_to_active(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        await move_to_testing(client, h["id"])
        await client.patch(f"{API}/{h['id']}", json={"status": "inconclusive", "outcome": {"result": "Synthetic test conclusion"}})
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    async def test_cannot_go_from_draft_to_testing(self, client: AsyncClient):
        h = await create_hypothesis(client, status="draft")
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "testing"})
        assert resp.status_code == 409

    async def test_cannot_go_from_draft_to_supported(self, client: AsyncClient):
        h = await create_hypothesis(client, status="draft")
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "supported", "outcome": {"result": "Synthetic test conclusion"}})
        assert resp.status_code == 409

    async def test_revised_is_terminal(self, client: AsyncClient):
        """Once a hypothesis is revised, no further transitions are allowed."""
        # Create, move to testing, then to supported
        h = await create_hypothesis(client, status="active")
        await move_to_testing(client, h["id"])
        await client.patch(f"{API}/{h['id']}", json={"status": "supported", "outcome": {"result": "Synthetic test conclusion"}})
        # Revise it
        await client.post(
            f"{API}/{h['id']}/revise",
            json={
                "statement": "Revised version",
                "rationale": "Original was too broad",
                "created_by": "tester",
            },
        )
        # Try to transition — should fail
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "active"})
        assert resp.status_code == 409

    async def test_archive_from_any_status(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "archived"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    async def test_unarchive_to_active(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        await client.patch(f"{API}/{h['id']}", json={"status": "archived"})
        resp = await client.patch(f"{API}/{h['id']}", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"


# ── Delete (Archive) ──────────────────────────────────────────────

class TestDeleteHypothesis:
    async def test_delete_archives(self, client: AsyncClient):
        created = await create_hypothesis(client)
        resp = await client.delete(f"{API}/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["is_archived"] is True

    async def test_delete_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API}/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    async def test_delete_idempotent(self, client: AsyncClient):
        created = await create_hypothesis(client)
        await client.delete(f"{API}/{created['id']}")
        resp = await client.delete(f"{API}/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["is_archived"] is True


# ── Stats ─────────────────────────────────────────────────────────

class TestStats:
    async def test_stats_returns_structure(self, client: AsyncClient):
        resp = await client.get(f"{API}/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "by_status" in body
        assert "avg_confidence" in body
        assert "total_evidence" in body
