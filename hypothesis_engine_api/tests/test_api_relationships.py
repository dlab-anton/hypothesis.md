"""API integration tests for hypothesis relationships (hierarchy, competition, dependency)."""

import pytest
from httpx import AsyncClient

API_HYPOTHESES = "/api/v1/hypotheses"


# ── Helpers ───────────────────────────────────────────────────────

async def create_hypothesis(client: AsyncClient, **overrides) -> dict:
    payload = {"statement": "Test hypothesis", "created_by": "agent-alpha"}
    payload.update(overrides)
    resp = await client.post(API_HYPOTHESES, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_relationship(
    client: AsyncClient, source_id: str, target_id: str,
    relationship_type: str = "decomposes_into", created_by: str = "agent-alpha",
) -> dict:
    resp = await client.post(
        f"{API_HYPOTHESES}/{source_id}/relationships",
        json={
            "target_hypothesis_id": target_id,
            "relationship_type": relationship_type,
            "created_by": created_by,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def add_evidence(client: AsyncClient, hypothesis_id: str, **overrides) -> dict:
    payload = {
        "content": "Test evidence",
        "evidence_type": "supporting",
        "created_by": "agent-alpha",
    }
    payload.update(overrides)
    resp = await client.post(f"{API_HYPOTHESES}/{hypothesis_id}/evidence", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def update_status(client: AsyncClient, hypothesis_id: str, status: str, created_by: str = "agent-alpha") -> dict:
    resp = await client.patch(
        f"{API_HYPOTHESES}/{hypothesis_id}",
        json={"status": status, "created_by": created_by},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def get_timeline(client: AsyncClient, hypothesis_id: str) -> list:
    resp = await client.get(f"{API_HYPOTHESES}/{hypothesis_id}/timeline")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── POST /hypotheses/{id}/relationships ───────────────────────────

class TestCreateRelationship:
    async def test_create_decomposes_into(self, client: AsyncClient):
        parent = await create_hypothesis(client, statement="Parent hypothesis")
        child = await create_hypothesis(client, statement="Child hypothesis")
        rel = await create_relationship(client, parent["id"], child["id"], "decomposes_into")
        assert rel["source_hypothesis_id"] == parent["id"]
        assert rel["target_hypothesis_id"] == child["id"]
        assert rel["relationship_type"] == "decomposes_into"

    async def test_create_competes_with(self, client: AsyncClient):
        h1 = await create_hypothesis(client, statement="Hypothesis A")
        h2 = await create_hypothesis(client, statement="Hypothesis B")
        rel = await create_relationship(client, h1["id"], h2["id"], "competes_with")
        assert rel["relationship_type"] == "competes_with"

    async def test_create_depends_on(self, client: AsyncClient):
        h1 = await create_hypothesis(client, statement="Depends on something")
        h2 = await create_hypothesis(client, statement="The dependency")
        rel = await create_relationship(client, h1["id"], h2["id"], "depends_on")
        assert rel["relationship_type"] == "depends_on"

    async def test_reject_self_reference(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.post(
            f"{API_HYPOTHESES}/{h['id']}/relationships",
            json={
                "target_hypothesis_id": h["id"],
                "relationship_type": "decomposes_into",
                "created_by": "agent-alpha",
            },
        )
        assert resp.status_code == 400

    async def test_reject_duplicate(self, client: AsyncClient):
        h1 = await create_hypothesis(client, statement="A")
        h2 = await create_hypothesis(client, statement="B")
        await create_relationship(client, h1["id"], h2["id"], "decomposes_into")
        resp = await client.post(
            f"{API_HYPOTHESES}/{h1['id']}/relationships",
            json={
                "target_hypothesis_id": h2["id"],
                "relationship_type": "decomposes_into",
                "created_by": "agent-alpha",
            },
        )
        assert resp.status_code == 409

    async def test_reject_symmetric_duplicate(self, client: AsyncClient):
        """competes_with is symmetric: H1→H2 blocks H2→H1."""
        h1 = await create_hypothesis(client, statement="Option A")
        h2 = await create_hypothesis(client, statement="Option B")
        await create_relationship(client, h1["id"], h2["id"], "competes_with")

        # Reverse direction should be rejected
        resp = await client.post(
            f"{API_HYPOTHESES}/{h2['id']}/relationships",
            json={
                "target_hypothesis_id": h1["id"],
                "relationship_type": "competes_with",
                "created_by": "agent-beta",
            },
        )
        assert resp.status_code == 409

    async def test_allow_reverse_for_directed_types(self, client: AsyncClient):
        """Directed types (depends_on) allow both directions — A depends on B and B depends on A are different."""
        h1 = await create_hypothesis(client, statement="A")
        h2 = await create_hypothesis(client, statement="B")
        await create_relationship(client, h1["id"], h2["id"], "depends_on")

        # Reverse should be allowed for directed types
        rel = await create_relationship(client, h2["id"], h1["id"], "depends_on")
        assert rel["source_hypothesis_id"] == h2["id"]

    async def test_reject_nonexistent_target(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.post(
            f"{API_HYPOTHESES}/{h['id']}/relationships",
            json={
                "target_hypothesis_id": "00000000-0000-0000-0000-000000000000",
                "relationship_type": "decomposes_into",
                "created_by": "agent-alpha",
            },
        )
        assert resp.status_code == 404

    async def test_reject_invalid_type(self, client: AsyncClient):
        h1 = await create_hypothesis(client, statement="A")
        h2 = await create_hypothesis(client, statement="B")
        resp = await client.post(
            f"{API_HYPOTHESES}/{h1['id']}/relationships",
            json={
                "target_hypothesis_id": h2["id"],
                "relationship_type": "invalid_type",
                "created_by": "agent-alpha",
            },
        )
        assert resp.status_code == 422

    async def test_emits_events_on_both_hypotheses(self, client: AsyncClient):
        h1 = await create_hypothesis(client, statement="Parent")
        h2 = await create_hypothesis(client, statement="Child")
        await create_relationship(client, h1["id"], h2["id"], "decomposes_into")

        # Both hypotheses should have a relationship_created event
        t1 = await get_timeline(client, h1["id"])
        t2 = await get_timeline(client, h2["id"])
        assert any(e["event_type"] == "relationship_created" for e in t1)
        assert any(e["event_type"] == "relationship_created" for e in t2)

    async def test_metadata_stored(self, client: AsyncClient):
        h1 = await create_hypothesis(client, statement="A")
        h2 = await create_hypothesis(client, statement="B")
        resp = await client.post(
            f"{API_HYPOTHESES}/{h1['id']}/relationships",
            json={
                "target_hypothesis_id": h2["id"],
                "relationship_type": "competes_with",
                "created_by": "agent-alpha",
                "metadata": {"reason": "mutually exclusive"},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["metadata"] == {"reason": "mutually exclusive"}


# ── GET /hypotheses/{id}/relationships ────────────────────────────

class TestListRelationships:
    async def test_lists_both_directions(self, client: AsyncClient):
        h1 = await create_hypothesis(client, statement="A")
        h2 = await create_hypothesis(client, statement="B")
        await create_relationship(client, h1["id"], h2["id"], "decomposes_into")

        # Source side
        resp = await client.get(f"{API_HYPOTHESES}/{h1['id']}/relationships")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        # Target side
        resp = await client.get(f"{API_HYPOTHESES}/{h2['id']}/relationships")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_filter_by_type(self, client: AsyncClient):
        h1 = await create_hypothesis(client, statement="A")
        h2 = await create_hypothesis(client, statement="B")
        h3 = await create_hypothesis(client, statement="C")
        await create_relationship(client, h1["id"], h2["id"], "decomposes_into")
        await create_relationship(client, h1["id"], h3["id"], "competes_with")

        resp = await client.get(
            f"{API_HYPOTHESES}/{h1['id']}/relationships",
            params={"relationship_type": "decomposes_into"},
        )
        assert len(resp.json()) == 1
        assert resp.json()[0]["relationship_type"] == "decomposes_into"

    async def test_empty_when_no_relationships(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.get(f"{API_HYPOTHESES}/{h['id']}/relationships")
        assert resp.status_code == 200
        assert resp.json() == []


# ── DELETE /hypotheses/{id}/relationships/{rel_id} ────────────────

class TestDeleteRelationship:
    async def test_delete_relationship(self, client: AsyncClient):
        h1 = await create_hypothesis(client, statement="A")
        h2 = await create_hypothesis(client, statement="B")
        rel = await create_relationship(client, h1["id"], h2["id"], "competes_with")

        resp = await client.delete(
            f"{API_HYPOTHESES}/{h1['id']}/relationships/{rel['id']}",
            params={"created_by": "agent-alpha"},
        )
        assert resp.status_code == 204

        # Verify it's gone
        resp = await client.get(f"{API_HYPOTHESES}/{h1['id']}/relationships")
        assert len(resp.json()) == 0

    async def test_delete_emits_removal_events(self, client: AsyncClient):
        h1 = await create_hypothesis(client, statement="A")
        h2 = await create_hypothesis(client, statement="B")
        rel = await create_relationship(client, h1["id"], h2["id"], "competes_with")

        await client.delete(
            f"{API_HYPOTHESES}/{h1['id']}/relationships/{rel['id']}",
            params={"created_by": "agent-alpha"},
        )

        t1 = await get_timeline(client, h1["id"])
        t2 = await get_timeline(client, h2["id"])
        assert any(e["event_type"] == "relationship_removed" for e in t1)
        assert any(e["event_type"] == "relationship_removed" for e in t2)

    async def test_delete_nonexistent_404(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.delete(
            f"{API_HYPOTHESES}/{h['id']}/relationships/00000000-0000-0000-0000-000000000000",
        )
        assert resp.status_code == 404


# ── GET /hypotheses/{id}/network ──────────────────────────────────

class TestNetwork:
    async def test_single_node_no_relationships(self, client: AsyncClient):
        h = await create_hypothesis(client)
        resp = await client.get(f"{API_HYPOTHESES}/{h['id']}/network")
        assert resp.status_code == 200
        body = resp.json()
        assert body["root_id"] == h["id"]
        assert len(body["nodes"]) == 1
        assert len(body["edges"]) == 0

    async def test_connected_graph(self, client: AsyncClient):
        parent = await create_hypothesis(client, statement="Parent")
        child1 = await create_hypothesis(client, statement="Child 1")
        child2 = await create_hypothesis(client, statement="Child 2")
        await create_relationship(client, parent["id"], child1["id"], "decomposes_into")
        await create_relationship(client, parent["id"], child2["id"], "decomposes_into")

        resp = await client.get(f"{API_HYPOTHESES}/{parent['id']}/network")
        body = resp.json()
        assert len(body["nodes"]) == 3
        assert len(body["edges"]) == 2

    async def test_transitive_walk(self, client: AsyncClient):
        """Network walks through multi-hop connections."""
        h1 = await create_hypothesis(client, statement="H1")
        h2 = await create_hypothesis(client, statement="H2")
        h3 = await create_hypothesis(client, statement="H3")
        await create_relationship(client, h1["id"], h2["id"], "decomposes_into")
        await create_relationship(client, h2["id"], h3["id"], "depends_on")

        resp = await client.get(f"{API_HYPOTHESES}/{h1['id']}/network")
        body = resp.json()
        assert len(body["nodes"]) == 3
        assert len(body["edges"]) == 2

    async def test_nonexistent_hypothesis_404(self, client: AsyncClient):
        resp = await client.get(
            f"{API_HYPOTHESES}/00000000-0000-0000-0000-000000000000/network"
        )
        assert resp.status_code == 404


# ── Event Propagation ─────────────────────────────────────────────

class TestEventPropagation:
    async def test_child_evidence_propagates_to_parent(self, client: AsyncClient):
        """Evidence on a child emits child_evidence_added on the parent."""
        parent = await create_hypothesis(client, statement="Parent")
        child = await create_hypothesis(client, statement="Child")
        await create_relationship(client, parent["id"], child["id"], "decomposes_into")

        await add_evidence(client, child["id"], content="Found something")

        timeline = await get_timeline(client, parent["id"])
        propagated = [e for e in timeline if e["event_type"] == "child_evidence_added"]
        assert len(propagated) == 1
        assert propagated[0]["data"]["source_hypothesis_id"] == child["id"]
        assert propagated[0]["data"]["evidence_type"] == "supporting"

    async def test_competing_evidence_propagates(self, client: AsyncClient):
        """Evidence on one competitor emits competing_evidence_added on the other."""
        h1 = await create_hypothesis(client, statement="Option A")
        h2 = await create_hypothesis(client, statement="Option B")
        await create_relationship(client, h1["id"], h2["id"], "competes_with")

        await add_evidence(client, h1["id"], content="Evidence for A")

        timeline = await get_timeline(client, h2["id"])
        propagated = [e for e in timeline if e["event_type"] == "competing_evidence_added"]
        assert len(propagated) == 1
        assert propagated[0]["data"]["source_hypothesis_id"] == h1["id"]

    async def test_dependency_evidence_propagates(self, client: AsyncClient):
        """Evidence on a dependency emits dependency_evidence_added on the dependent."""
        dependent = await create_hypothesis(client, statement="Depends on B")
        dependency = await create_hypothesis(client, statement="The dependency")
        await create_relationship(client, dependent["id"], dependency["id"], "depends_on")

        await add_evidence(client, dependency["id"], content="Dep evidence")

        timeline = await get_timeline(client, dependent["id"])
        propagated = [e for e in timeline if e["event_type"] == "dependency_evidence_added"]
        assert len(propagated) == 1

    async def test_child_status_change_propagates_to_parent(self, client: AsyncClient):
        """Status change on a child emits child_status_changed on the parent."""
        parent = await create_hypothesis(client, statement="Parent")
        child = await create_hypothesis(client, statement="Child")
        await create_relationship(client, parent["id"], child["id"], "decomposes_into")

        # Move child through lifecycle
        await update_status(client, child["id"], "active")
        await update_status(client, child["id"], "testing")

        timeline = await get_timeline(client, parent["id"])
        propagated = [e for e in timeline if e["event_type"] == "child_status_changed"]
        assert len(propagated) == 2

    async def test_competing_status_change_propagates(self, client: AsyncClient):
        """Status change on one competitor emits competing_status_changed on the other."""
        h1 = await create_hypothesis(client, statement="Option A")
        h2 = await create_hypothesis(client, statement="Option B")
        await create_relationship(client, h1["id"], h2["id"], "competes_with")

        await update_status(client, h1["id"], "active")

        timeline = await get_timeline(client, h2["id"])
        propagated = [e for e in timeline if e["event_type"] == "competing_status_changed"]
        assert len(propagated) == 1
        assert propagated[0]["data"]["new_status"] == "active"

    async def test_no_propagation_without_relationship(self, client: AsyncClient):
        """Unrelated hypotheses don't get propagated events."""
        h1 = await create_hypothesis(client, statement="Standalone A")
        h2 = await create_hypothesis(client, statement="Standalone B")

        await add_evidence(client, h1["id"], content="Some evidence")

        timeline = await get_timeline(client, h2["id"])
        propagated = [e for e in timeline if "competing" in e["event_type"] or "child" in e["event_type"]]
        assert len(propagated) == 0
