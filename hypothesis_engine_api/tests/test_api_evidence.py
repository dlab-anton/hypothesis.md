"""API integration tests for evidence endpoints."""

import pytest
from httpx import AsyncClient

API = "/api/v1/hypotheses"


async def create_hypothesis(client: AsyncClient, **overrides) -> dict:
    payload = {"statement": "Evidence test hypothesis", "created_by": "test-agent", "status": "active"}
    payload.update(overrides)
    resp = await client.post(API, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def add_evidence(client: AsyncClient, hypothesis_id: str, **overrides) -> dict:
    payload = {
        "content": "Default evidence content",
        "evidence_type": "supporting",
        "created_by": "test-agent",
    }
    payload.update(overrides)
    resp = await client.post(f"{API}/{hypothesis_id}/evidence", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Add Evidence ──────────────────────────────────────────────────

class TestAddEvidence:
    async def test_add_supporting(self, client: AsyncClient):
        h = await create_hypothesis(client)
        result = await add_evidence(client, h["id"], evidence_type="supporting")
        assert result["evidence"]["evidence_type"] == "supporting"
        assert result["evidence"]["hypothesis_id"] == h["id"]
        assert result["hypothesis"]["id"] == h["id"]

    async def test_add_contradicting(self, client: AsyncClient):
        h = await create_hypothesis(client)
        result = await add_evidence(client, h["id"], evidence_type="contradicting")
        assert result["evidence"]["evidence_type"] == "contradicting"

    async def test_add_neutral(self, client: AsyncClient):
        h = await create_hypothesis(client)
        result = await add_evidence(client, h["id"], evidence_type="neutral")
        assert result["evidence"]["evidence_type"] == "neutral"

    async def test_add_with_source_and_strength(self, client: AsyncClient):
        h = await create_hypothesis(client)
        result = await add_evidence(
            client,
            h["id"],
            content="pg_stat_activity shows 20/20",
            source="psql query",
            strength=0.9,
        )
        ev = result["evidence"]
        assert ev["source"] == "psql query"
        assert ev["strength"] == 0.9

    async def test_add_updates_evidence_counts(self, client: AsyncClient):
        h = await create_hypothesis(client)
        result = await add_evidence(client, h["id"], evidence_type="supporting")
        counts = result["hypothesis"]["evidence_counts"]
        assert counts["supporting"] == 1
        assert counts["contradicting"] == 0
        assert counts["neutral"] == 0

    async def test_add_multiple_updates_counts(self, client: AsyncClient):
        h = await create_hypothesis(client)
        await add_evidence(client, h["id"], evidence_type="supporting")
        await add_evidence(client, h["id"], evidence_type="contradicting")
        result = await add_evidence(client, h["id"], evidence_type="supporting")
        counts = result["hypothesis"]["evidence_counts"]
        assert counts["supporting"] == 2
        assert counts["contradicting"] == 1

    async def test_add_with_confidence_update(self, client: AsyncClient):
        h = await create_hypothesis(client, confidence=0.5)
        result = await add_evidence(client, h["id"], confidence=0.8)
        assert result["hypothesis"]["confidence"] == 0.8
        assert result["evidence"]["confidence_after"] == 0.8

    async def test_add_without_confidence_keeps_original(self, client: AsyncClient):
        h = await create_hypothesis(client, confidence=0.6)
        result = await add_evidence(client, h["id"])
        assert result["hypothesis"]["confidence"] == 0.6
        assert result["evidence"]["confidence_after"] == 0.6

    async def test_confidence_after_tracks_progression(self, client: AsyncClient):
        """Evidence list becomes a confidence time series."""
        h = await create_hypothesis(client, confidence=0.5)
        await add_evidence(client, h["id"], content="First clue", confidence=0.6)
        await add_evidence(client, h["id"], content="Strong signal", confidence=0.75)
        await add_evidence(client, h["id"], content="Counter-evidence", confidence=0.55)

        resp = await client.get(f"{API}/{h['id']}/evidence")
        items = resp.json()["items"]
        # Listed newest-first
        assert items[0]["confidence_after"] == 0.55
        assert items[1]["confidence_after"] == 0.75
        assert items[2]["confidence_after"] == 0.6

    async def test_add_to_nonexistent_hypothesis(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/00000000-0000-0000-0000-000000000000/evidence",
            json={"content": "T", "evidence_type": "supporting", "created_by": "x"},
        )
        assert resp.status_code == 404

    async def test_add_invalid_type_rejected(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.post(
            f"{API}/{h['id']}/evidence",
            json={"content": "T", "evidence_type": "invalid", "created_by": "x"},
        )
        assert resp.status_code == 422

    async def test_add_empty_content_rejected(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.post(
            f"{API}/{h['id']}/evidence",
            json={"content": "", "evidence_type": "supporting", "created_by": "x"},
        )
        assert resp.status_code == 422


# ── List Evidence ─────────────────────────────────────────────────

class TestListEvidence:
    async def test_list_empty(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.get(f"{API}/{h['id']}/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_returns_added(self, client: AsyncClient):
        h = await create_hypothesis(client)
        await add_evidence(client, h["id"], content="Evidence 1")
        await add_evidence(client, h["id"], content="Evidence 2")
        resp = await client.get(f"{API}/{h['id']}/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_filter_by_type(self, client: AsyncClient):
        h = await create_hypothesis(client)
        await add_evidence(client, h["id"], evidence_type="supporting")
        await add_evidence(client, h["id"], evidence_type="contradicting")
        resp = await client.get(f"{API}/{h['id']}/evidence", params={"evidence_type": "supporting"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["evidence_type"] == "supporting"

    async def test_list_ordered_by_created_at_desc(self, client: AsyncClient):
        h = await create_hypothesis(client)
        await add_evidence(client, h["id"], content="First")
        await add_evidence(client, h["id"], content="Second")
        resp = await client.get(f"{API}/{h['id']}/evidence")
        data = resp.json()
        assert data["items"][0]["content"] == "Second"
        assert data["items"][1]["content"] == "First"

    async def test_list_for_nonexistent_hypothesis(self, client: AsyncClient):
        resp = await client.get(f"{API}/00000000-0000-0000-0000-000000000000/evidence")
        assert resp.status_code == 404


# ── Confidence Contradiction Warning ─────────────────────────────

class TestConfidenceContradictionWarning:
    async def test_contradicting_evidence_with_raised_confidence_emits_warning(self, client: AsyncClient):
        """Adding contradicting evidence while raising confidence should emit a warning event."""
        h = await create_hypothesis(client, confidence=0.5)
        await add_evidence(
            client, h["id"],
            evidence_type="contradicting",
            content="Evidence against the hypothesis",
            confidence=0.8,  # Raising confidence despite contradicting evidence
        )
        resp = await client.get(f"{API}/{h['id']}/timeline")
        events = resp.json()
        warning_events = [e for e in events if e["event_type"] == "confidence_contradiction_warning"]
        assert len(warning_events) == 1
        assert warning_events[0]["data"]["old_confidence"] == 0.5
        assert warning_events[0]["data"]["new_confidence"] == 0.8
        assert "confirmation bias" in warning_events[0]["data"]["warning"].lower()

    async def test_contradicting_evidence_with_lowered_confidence_no_warning(self, client: AsyncClient):
        """Adding contradicting evidence while lowering confidence should NOT emit a warning."""
        h = await create_hypothesis(client, confidence=0.8)
        await add_evidence(
            client, h["id"],
            evidence_type="contradicting",
            content="Evidence against",
            confidence=0.4,  # Appropriately lowering confidence
        )
        resp = await client.get(f"{API}/{h['id']}/timeline")
        events = resp.json()
        warning_events = [e for e in events if e["event_type"] == "confidence_contradiction_warning"]
        assert len(warning_events) == 0

    async def test_supporting_evidence_with_raised_confidence_no_warning(self, client: AsyncClient):
        """Adding supporting evidence while raising confidence should NOT emit a warning."""
        h = await create_hypothesis(client, confidence=0.5)
        await add_evidence(
            client, h["id"],
            evidence_type="supporting",
            content="Evidence for the hypothesis",
            confidence=0.8,
        )
        resp = await client.get(f"{API}/{h['id']}/timeline")
        events = resp.json()
        warning_events = [e for e in events if e["event_type"] == "confidence_contradiction_warning"]
        assert len(warning_events) == 0
