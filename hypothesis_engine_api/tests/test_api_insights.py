"""API integration tests for channel insights endpoints."""

import uuid

import pytest
from httpx import AsyncClient

API_INSIGHTS = "/api/v1/insights"


# ── Helpers ───────────────────────────────────────────────────────

async def create_insight(client: AsyncClient, **overrides) -> dict:
    payload = {
        "channel": "debugging",
        "insight_type": "calibration",
        "content": "I'm overconfident on timing predictions",
        "created_by": "agent-alpha",
    }
    payload.update(overrides)
    resp = await client.post(API_INSIGHTS, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── POST /insights ────────────────────────────────────────────────

class TestCreateInsight:
    async def test_create_minimal(self, client: AsyncClient):
        data = await create_insight(client)
        assert data["channel"] == "debugging"
        assert data["insight_type"] == "calibration"
        assert data["content"] == "I'm overconfident on timing predictions"
        assert data["created_by"] == "agent-alpha"
        assert data["metadata"] is None
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_with_metadata(self, client: AsyncClient):
        data = await create_insight(
            client,
            metadata={"accuracy": 0.45, "based_on": ["uuid1"]},
        )
        assert data["metadata"]["accuracy"] == 0.45
        assert data["metadata"]["based_on"] == ["uuid1"]

    async def test_channel_auto_lowercase(self, client: AsyncClient):
        data = await create_insight(client, channel="Stock Predictions")
        assert data["channel"] == "stock-predictions"

    async def test_all_insight_types(self, client: AsyncClient):
        for t in ["calibration", "bias", "prior", "pattern"]:
            data = await create_insight(client, insight_type=t, content=f"Test {t}")
            assert data["insight_type"] == t

    async def test_invalid_type_rejected(self, client: AsyncClient):
        resp = await client.post(API_INSIGHTS, json={
            "channel": "test", "insight_type": "invalid",
            "content": "T", "created_by": "x",
        })
        assert resp.status_code == 422

    async def test_empty_content_rejected(self, client: AsyncClient):
        resp = await client.post(API_INSIGHTS, json={
            "channel": "test", "insight_type": "calibration",
            "content": "", "created_by": "x",
        })
        assert resp.status_code == 422

    async def test_missing_channel_rejected(self, client: AsyncClient):
        resp = await client.post(API_INSIGHTS, json={
            "insight_type": "calibration", "content": "T", "created_by": "x",
        })
        assert resp.status_code == 422


# ── GET /insights ─────────────────────────────────────────────────

class TestListInsights:
    async def test_empty_list(self, client: AsyncClient):
        resp = await client.get(API_INSIGHTS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_all(self, client: AsyncClient):
        await create_insight(client, content="Insight 1")
        await create_insight(client, content="Insight 2")
        resp = await client.get(API_INSIGHTS)
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_filter_by_channel(self, client: AsyncClient):
        await create_insight(client, channel="debugging")
        await create_insight(client, channel="trading")
        resp = await client.get(API_INSIGHTS, params={"channel": "debugging"})
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["channel"] == "debugging"

    async def test_filter_by_type(self, client: AsyncClient):
        await create_insight(client, insight_type="calibration")
        await create_insight(client, insight_type="bias", content="Bias insight")
        resp = await client.get(API_INSIGHTS, params={"type": "bias"})
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["insight_type"] == "bias"

    async def test_filter_by_created_by(self, client: AsyncClient):
        await create_insight(client, created_by="agent-alpha")
        await create_insight(client, created_by="agent-beta", content="Beta insight")
        resp = await client.get(API_INSIGHTS, params={"created_by": "agent-beta"})
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["created_by"] == "agent-beta"

    async def test_pagination(self, client: AsyncClient):
        for i in range(5):
            await create_insight(client, content=f"Insight {i}")
        resp = await client.get(API_INSIGHTS, params={"skip": 2, "limit": 2})
        data = resp.json()
        assert len(data["items"]) == 2

    async def test_ordered_by_updated_at_desc(self, client: AsyncClient):
        i1 = await create_insight(client, content="First")
        i2 = await create_insight(client, content="Second")
        resp = await client.get(API_INSIGHTS)
        data = resp.json()
        assert data["items"][0]["id"] == i2["id"]
        assert data["items"][1]["id"] == i1["id"]


# ── GET /insights/{id} ───────────────────────────────────────────

class TestGetInsight:
    async def test_get_existing(self, client: AsyncClient):
        created = await create_insight(client)
        resp = await client.get(f"{API_INSIGHTS}/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    async def test_get_nonexistent(self, client: AsyncClient):
        resp = await client.get(f"{API_INSIGHTS}/{uuid.uuid4()}")
        assert resp.status_code == 404


# ── PATCH /insights/{id} ─────────────────────────────────────────

class TestUpdateInsight:
    async def test_update_content(self, client: AsyncClient):
        created = await create_insight(client)
        resp = await client.patch(
            f"{API_INSIGHTS}/{created['id']}",
            json={"content": "Updated: I'm VERY overconfident on timing", "updated_by": "agent-beta"},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated: I'm VERY overconfident on timing"
        assert resp.json()["channel"] == created["channel"]
        assert resp.json()["updated_by"] == "agent-beta"

    async def test_update_metadata(self, client: AsyncClient):
        created = await create_insight(client)
        resp = await client.patch(
            f"{API_INSIGHTS}/{created['id']}",
            json={"metadata": {"accuracy": 0.45}, "updated_by": "agent-beta"},
        )
        assert resp.status_code == 200
        assert resp.json()["metadata"]["accuracy"] == 0.45
        assert resp.json()["updated_by"] == "agent-beta"

    async def test_partial_update_preserves_other_fields(self, client: AsyncClient):
        created = await create_insight(
            client,
            content="Original",
            metadata={"key": "value"},
        )
        resp = await client.patch(
            f"{API_INSIGHTS}/{created['id']}",
            json={"content": "Updated", "updated_by": "agent-alpha"},
        )
        data = resp.json()
        assert data["content"] == "Updated"
        assert data["metadata"]["key"] == "value"

    async def test_updated_by_tracks_who_changed_it(self, client: AsyncClient):
        """Agent A creates insight, agent B updates it — updated_by reflects B."""
        created = await create_insight(client, created_by="agent-alpha")
        assert created["updated_by"] is None
        resp = await client.patch(
            f"{API_INSIGHTS}/{created['id']}",
            json={"content": "Agent B's revision", "updated_by": "agent-beta"},
        )
        data = resp.json()
        assert data["created_by"] == "agent-alpha"
        assert data["updated_by"] == "agent-beta"

    async def test_update_nonexistent(self, client: AsyncClient):
        resp = await client.patch(
            f"{API_INSIGHTS}/{uuid.uuid4()}",
            json={"content": "Updated", "updated_by": "x"},
        )
        assert resp.status_code == 404

    async def test_update_missing_updated_by_rejected(self, client: AsyncClient):
        created = await create_insight(client)
        resp = await client.patch(
            f"{API_INSIGHTS}/{created['id']}",
            json={"content": "Updated"},
        )
        assert resp.status_code == 422


# ── DELETE /insights/{id} ─────────────────────────────────────────

class TestDeleteInsight:
    async def test_delete_existing(self, client: AsyncClient):
        created = await create_insight(client)
        resp = await client.delete(f"{API_INSIGHTS}/{created['id']}")
        assert resp.status_code == 204

        # Verify it's gone
        resp = await client.get(f"{API_INSIGHTS}/{created['id']}")
        assert resp.status_code == 404

    async def test_delete_nonexistent(self, client: AsyncClient):
        resp = await client.delete(f"{API_INSIGHTS}/{uuid.uuid4()}")
        assert resp.status_code == 404


# ── Cross-Agent Visibility ────────────────────────────────────────

class TestCrossAgentVisibility:
    async def test_agent_b_sees_agent_a_insights(self, client: AsyncClient):
        """Insights created by one agent are visible to all agents."""
        await create_insight(
            client,
            channel="shared-domain",
            content="Momentum signals are unreliable",
            created_by="agent-alpha",
        )
        # Agent beta queries the same channel
        resp = await client.get(
            API_INSIGHTS,
            params={"channel": "shared-domain"},
        )
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["created_by"] == "agent-alpha"
        assert data["items"][0]["content"] == "Momentum signals are unreliable"

    async def test_multiple_agents_same_channel(self, client: AsyncClient):
        """Multiple agents can contribute insights to the same channel."""
        await create_insight(
            client,
            channel="trading",
            content="Alpha's calibration insight",
            created_by="agent-alpha",
        )
        await create_insight(
            client,
            channel="trading",
            content="Beta's bias insight",
            created_by="agent-beta",
            insight_type="bias",
        )
        resp = await client.get(API_INSIGHTS, params={"channel": "trading"})
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        agents = {d["created_by"] for d in data["items"]}
        assert agents == {"agent-alpha", "agent-beta"}
