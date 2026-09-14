"""API integration tests for timeline, lineage, and revise endpoints."""

import pytest
from httpx import AsyncClient

API = "/api/v1/hypotheses"


async def create_hypothesis(client: AsyncClient, **overrides) -> dict:
    payload = {"statement": "Timeline test hypothesis", "created_by": "test-agent", "status": "active"}
    payload.update(overrides)
    resp = await client.post(API, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def move_to_testing(client: AsyncClient, hypothesis_id: str) -> dict:
    resp = await client.patch(f"{API}/{hypothesis_id}", json={"status": "testing"})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def move_to_supported(client: AsyncClient, hypothesis_id: str) -> dict:
    """Helper: active → testing → supported."""
    await move_to_testing(client, hypothesis_id)
    resp = await client.patch(f"{API}/{hypothesis_id}", json={"status": "supported", "outcome": {"result": "Synthetic test conclusion"}})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Timeline ──────────────────────────────────────────────────────

class TestTimeline:
    async def test_timeline_has_created_event(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.get(f"{API}/{h['id']}/timeline")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 1
        assert events[0]["event_type"] == "created"
        assert events[0]["hypothesis_id"] == h["id"]

    async def test_timeline_records_status_change(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        await client.patch(f"{API}/{h['id']}", json={"status": "testing"})
        resp = await client.get(f"{API}/{h['id']}/timeline")
        events = resp.json()
        status_events = [e for e in events if e["event_type"] == "status_changed"]
        assert len(status_events) >= 1
        latest = status_events[-1]
        assert latest["data"]["old_status"] == "active"
        assert latest["data"]["new_status"] == "testing"

    async def test_timeline_records_confidence_change(self, client: AsyncClient):
        h = await create_hypothesis(client, confidence=0.5)
        await client.patch(f"{API}/{h['id']}", json={"confidence": 0.9})
        resp = await client.get(f"{API}/{h['id']}/timeline")
        events = resp.json()
        conf_events = [e for e in events if e["event_type"] == "confidence_changed"]
        assert len(conf_events) >= 1
        assert conf_events[-1]["data"]["new_confidence"] == 0.9

    async def test_timeline_records_evidence_added(self, client: AsyncClient):
        h = await create_hypothesis(client)
        await client.post(
            f"{API}/{h['id']}/evidence",
            json={"content": "Some evidence", "evidence_type": "supporting", "created_by": "x"},
        )
        resp = await client.get(f"{API}/{h['id']}/timeline")
        events = resp.json()
        ev_events = [e for e in events if e["event_type"] == "evidence_added"]
        assert len(ev_events) >= 1
        assert ev_events[-1]["data"]["evidence_type"] == "supporting"

    async def test_timeline_records_archive(self, client: AsyncClient):
        h = await create_hypothesis(client)
        await client.delete(f"{API}/{h['id']}")
        resp = await client.get(f"{API}/{h['id']}/timeline")
        events = resp.json()
        archive_events = [e for e in events if e["event_type"] == "archived"]
        assert len(archive_events) >= 1

    async def test_timeline_chronological_order(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active", confidence=0.3)
        await client.patch(f"{API}/{h['id']}", json={"confidence": 0.6})
        await client.patch(f"{API}/{h['id']}", json={"status": "testing"})
        resp = await client.get(f"{API}/{h['id']}/timeline")
        events = resp.json()
        timestamps = [e["created_at"] for e in events]
        assert timestamps == sorted(timestamps)

    async def test_timeline_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API}/00000000-0000-0000-0000-000000000000/timeline")
        assert resp.status_code == 404


# ── Lineage ───────────────────────────────────────────────────────

class TestLineage:
    async def test_lineage_single_hypothesis(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.get(f"{API}/{h['id']}/lineage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["current_id"] == h["id"]
        assert len(body["chain"]) == 1
        assert body["chain"][0]["id"] == h["id"]

    async def test_lineage_after_revision(self, client: AsyncClient):
        # Create original, move to supported (via testing), then revise
        original = await create_hypothesis(client, status="active")
        await move_to_supported(client, original["id"])
        revise_resp = await client.post(
            f"{API}/{original['id']}/revise",
            json={
                "statement": "Revised statement",
                "rationale": "Evidence showed the original was too broad",
                "created_by": "tester",
            },
        )
        assert revise_resp.status_code == 201
        revised = revise_resp.json()

        # Check lineage from the revised hypothesis
        resp = await client.get(f"{API}/{revised['id']}/lineage")
        body = resp.json()
        assert len(body["chain"]) == 2
        assert body["chain"][0]["id"] == original["id"]
        assert body["chain"][1]["id"] == revised["id"]

    async def test_lineage_from_original(self, client: AsyncClient):
        original = await create_hypothesis(client, status="active")
        await move_to_supported(client, original["id"])
        revise_resp = await client.post(
            f"{API}/{original['id']}/revise",
            json={
                "statement": "V2",
                "rationale": "Refined based on new evidence",
                "created_by": "tester",
            },
        )
        revised = revise_resp.json()

        # Check lineage from the original
        resp = await client.get(f"{API}/{original['id']}/lineage")
        body = resp.json()
        assert len(body["chain"]) == 2
        chain_ids = [h["id"] for h in body["chain"]]
        assert original["id"] in chain_ids
        assert revised["id"] in chain_ids

    async def test_lineage_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API}/00000000-0000-0000-0000-000000000000/lineage")
        assert resp.status_code == 404


# ── Revise ────────────────────────────────────────────────────────

class TestRevise:
    async def test_revise_creates_new_hypothesis(self, client: AsyncClient):
        original = await create_hypothesis(client, status="active")
        await move_to_supported(client, original["id"])
        resp = await client.post(
            f"{API}/{original['id']}/revise",
            json={
                "statement": "Refined hypothesis",
                "rationale": "Original was too broad based on testing results",
                "created_by": "tester",
                "confidence": 0.6,
            },
        )
        assert resp.status_code == 201
        revised = resp.json()
        assert revised["statement"] == "Refined hypothesis"
        assert revised["status"] == "active"
        assert revised["confidence"] == 0.6
        assert revised["parent_id"] == original["id"]

    async def test_revise_with_falsification_criteria(self, client: AsyncClient):
        original = await create_hypothesis(client, status="active")
        await move_to_supported(client, original["id"])
        resp = await client.post(
            f"{API}/{original['id']}/revise",
            json={
                "statement": "Refined hypothesis",
                "falsification_criteria": "If Y then this new version is wrong",
                "rationale": "Original missed a key variable",
                "created_by": "tester",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["falsification_criteria"] == "If Y then this new version is wrong"

    async def test_revise_with_deadline_and_metadata(self, client: AsyncClient):
        original = await create_hypothesis(client, status="active")
        await move_to_supported(client, original["id"])
        resp = await client.post(
            f"{API}/{original['id']}/revise",
            json={
                "statement": "Revised with deadline",
                "rationale": "Extended timeline based on new data",
                "created_by": "tester",
                "deadline": "2026-08-01T00:00:00Z",
                "metadata": {"ticker": "ACME", "target_price": 7.5},
            },
        )
        assert resp.status_code == 201
        revised = resp.json()
        assert "2026-08-01" in revised["deadline"]
        assert revised["metadata"] == {"ticker": "ACME", "target_price": 7.5}

    async def test_revise_with_formal_methodology(self, client: AsyncClient):
        original = await create_hypothesis(client, status="active")
        await move_to_supported(client, original["id"])
        design = {"independent_variable": "Time", "control": "S&P 500", "lessons_from_v1": "Monitor weekly"}
        resp = await client.post(
            f"{API}/{original['id']}/revise",
            json={
                "statement": "Revised with formal methodology",
                "rationale": "H0 not rejected but trajectory positive",
                "created_by": "tester",
                "null_hypothesis": "Target will NOT be reached in extended period",
                "experimental_design": design,
                "significance_level": 0.05,
            },
        )
        assert resp.status_code == 201
        revised = resp.json()
        assert revised["null_hypothesis"] == "Target will NOT be reached in extended period"
        assert revised["experimental_design"] == design
        assert revised["significance_level"] == 0.05

    async def test_revise_marks_original_as_revised(self, client: AsyncClient):
        original = await create_hypothesis(client, status="active")
        await move_to_supported(client, original["id"])
        await client.post(
            f"{API}/{original['id']}/revise",
            json={
                "statement": "V2",
                "rationale": "Evidence contradicted the original",
                "created_by": "tester",
            },
        )
        resp = await client.get(f"{API}/{original['id']}")
        assert resp.json()["status"] == "revised"

    async def test_revise_from_refuted(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        await move_to_testing(client, h["id"])
        await client.patch(f"{API}/{h['id']}", json={"status": "refuted", "outcome": {"result": "Synthetic test conclusion"}})
        resp = await client.post(
            f"{API}/{h['id']}/revise",
            json={
                "statement": "V2 from refuted",
                "rationale": "Refutation pointed to a better theory",
                "created_by": "tester",
            },
        )
        assert resp.status_code == 201

    async def test_revise_from_inconclusive(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        await move_to_testing(client, h["id"])
        await client.patch(f"{API}/{h['id']}", json={"status": "inconclusive", "outcome": {"result": "Synthetic test conclusion"}})
        resp = await client.post(
            f"{API}/{h['id']}/revise",
            json={
                "statement": "V2 from inconclusive",
                "rationale": "Need a more specific, testable claim",
                "created_by": "tester",
            },
        )
        assert resp.status_code == 201

    async def test_cannot_revise_draft(self, client: AsyncClient):
        h = await create_hypothesis(client, status="draft")
        resp = await client.post(
            f"{API}/{h['id']}/revise",
            json={
                "statement": "V2",
                "rationale": "Some reason",
                "created_by": "tester",
            },
        )
        assert resp.status_code == 409

    async def test_cannot_revise_active(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        resp = await client.post(
            f"{API}/{h['id']}/revise",
            json={
                "statement": "V2",
                "rationale": "Some reason",
                "created_by": "tester",
            },
        )
        assert resp.status_code == 409

    async def test_cannot_revise_testing(self, client: AsyncClient):
        h = await create_hypothesis(client, status="active")
        await move_to_testing(client, h["id"])
        resp = await client.post(
            f"{API}/{h['id']}/revise",
            json={
                "statement": "V2",
                "rationale": "Some reason",
                "created_by": "tester",
            },
        )
        assert resp.status_code == 409

    async def test_revise_without_rationale_rejected(self, client: AsyncClient):
        """Revise requires a rationale explaining why."""
        h = await create_hypothesis(client, status="active")
        await move_to_supported(client, h["id"])
        resp = await client.post(
            f"{API}/{h['id']}/revise",
            json={"statement": "V2", "created_by": "tester"},
        )
        assert resp.status_code == 422

    async def test_revise_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/00000000-0000-0000-0000-000000000000/revise",
            json={
                "statement": "V2",
                "rationale": "Some reason",
                "created_by": "tester",
            },
        )
        assert resp.status_code == 404

    async def test_revise_emits_events_with_rationale(self, client: AsyncClient):
        original = await create_hypothesis(client, status="active")
        await move_to_supported(client, original["id"])
        await client.post(
            f"{API}/{original['id']}/revise",
            json={
                "statement": "V2",
                "rationale": "Evidence showed retry logic was the real cause",
                "created_by": "tester",
            },
        )
        resp = await client.get(f"{API}/{original['id']}/timeline")
        events = resp.json()
        event_types = [e["event_type"] for e in events]
        assert "revised" in event_types
        assert "status_changed" in event_types
        # Check rationale is recorded in the revised event
        revised_events = [e for e in events if e["event_type"] == "revised"]
        assert len(revised_events) >= 1
        assert revised_events[-1]["data"]["rationale"] == "Evidence showed retry logic was the real cause"
