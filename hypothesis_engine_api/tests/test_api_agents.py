"""API integration tests for agent coordination endpoints."""

import pytest
from httpx import AsyncClient

API_HYPOTHESES = "/api/v1/hypotheses"
API_AGENTS = "/api/v1/agents"
API_INBOX = "/api/v1/inbox"


# ── Helpers ───────────────────────────────────────────────────────

async def create_hypothesis(client: AsyncClient, **overrides) -> dict:
    payload = {"statement": "Agent test hypothesis", "created_by": "agent-alpha"}
    payload.update(overrides)
    resp = await client.post(API_HYPOTHESES, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def add_evidence(client: AsyncClient, hypothesis_id: str, **overrides) -> dict:
    payload = {
        "content": "Test evidence",
        "evidence_type": "supporting",
        "created_by": "agent-beta",
    }
    payload.update(overrides)
    resp = await client.post(f"{API_HYPOTHESES}/{hypothesis_id}/evidence", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── GET /agents ──────────────────────────────────────────────────

class TestListAgents:
    async def test_empty_when_no_data(self, client: AsyncClient):
        resp = await client.get(API_AGENTS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["agents"] == []

    async def test_agents_from_hypotheses(self, client: AsyncClient):
        await create_hypothesis(client, created_by="agent-alpha")
        await create_hypothesis(client, created_by="agent-beta")
        resp = await client.get(API_AGENTS)
        body = resp.json()
        names = [a["name"] for a in body["agents"]]
        assert "agent-alpha" in names
        assert "agent-beta" in names

    async def test_agent_from_evidence_only(self, client: AsyncClient):
        """An agent that only added evidence should appear."""
        h = await create_hypothesis(client, created_by="agent-alpha")
        await add_evidence(client, h["id"], created_by="evidence-only-agent")
        resp = await client.get(API_AGENTS)
        names = [a["name"] for a in resp.json()["agents"]]
        assert "evidence-only-agent" in names

    async def test_agent_summary_counts(self, client: AsyncClient):
        h = await create_hypothesis(client, created_by="agent-alpha", channel="test-channel")
        await add_evidence(client, h["id"], created_by="agent-alpha")
        resp = await client.get(API_AGENTS)
        alpha = next(a for a in resp.json()["agents"] if a["name"] == "agent-alpha")
        assert alpha["total_hypotheses"] >= 1
        assert alpha["total_evidence"] >= 1
        assert alpha["total_events"] >= 1
        assert "test-channel" in alpha["channels"]
        assert alpha["first_seen"] is not None
        assert alpha["last_active"] is not None

    async def test_agents_sorted_by_name(self, client: AsyncClient):
        await create_hypothesis(client, created_by="zeta-agent")
        await create_hypothesis(client, created_by="alpha-agent")
        resp = await client.get(API_AGENTS)
        names = [a["name"] for a in resp.json()["agents"]]
        assert names == sorted(names)


# ── GET /agents/{name}/activity ──────────────────────────────────

class TestAgentActivity:
    async def test_activity_returns_recent_actions(self, client: AsyncClient):
        h = await create_hypothesis(client, created_by="agent-alpha")
        await add_evidence(client, h["id"], created_by="agent-alpha")
        resp = await client.get(f"{API_AGENTS}/agent-alpha/activity")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent"] == "agent-alpha"
        assert len(body["hypotheses"]) >= 1
        assert len(body["evidence"]) >= 1
        assert len(body["events"]) >= 1

    async def test_activity_includes_hypothesis_statement(self, client: AsyncClient):
        h = await create_hypothesis(client, created_by="agent-alpha", statement="Specific test statement")
        await add_evidence(client, h["id"], created_by="agent-alpha")
        resp = await client.get(f"{API_AGENTS}/agent-alpha/activity")
        evidence = resp.json()["evidence"]
        assert any("Specific test statement" in e["hypothesis_statement"] for e in evidence)

    async def test_activity_with_since_filter(self, client: AsyncClient):
        await create_hypothesis(client, created_by="agent-alpha")
        resp = await client.get(f"{API_AGENTS}/agent-alpha/activity?since=2099-01-01T00:00:00Z")
        body = resp.json()
        assert body["hypotheses"] == []
        assert body["evidence"] == []
        assert body["events"] == []

    async def test_activity_with_limit(self, client: AsyncClient):
        for i in range(5):
            await create_hypothesis(client, created_by="agent-alpha", statement=f"H{i}")
        resp = await client.get(f"{API_AGENTS}/agent-alpha/activity?limit=2")
        assert len(resp.json()["hypotheses"]) <= 2

    async def test_activity_not_found_for_unknown_agent(self, client: AsyncClient):
        resp = await client.get(f"{API_AGENTS}/nonexistent-agent/activity")
        assert resp.status_code == 404


# ── GET /inbox ───────────────────────────────────────────────────

class TestInbox:
    async def test_inbox_shows_other_agent_actions(self, client: AsyncClient):
        """Alpha creates hypothesis, Beta adds evidence -> Alpha's inbox shows it."""
        h = await create_hypothesis(client, created_by="agent-alpha")
        await add_evidence(client, h["id"], created_by="agent-beta")
        resp = await client.get(f"{API_INBOX}?agent=agent-alpha")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent"] == "agent-alpha"
        assert body["total"] >= 1
        assert any(item["triggered_by"] == "agent-beta" for item in body["items"])

    async def test_inbox_excludes_own_actions(self, client: AsyncClient):
        """Alpha's own events should not appear in Alpha's inbox."""
        await create_hypothesis(client, created_by="agent-alpha")
        resp = await client.get(f"{API_INBOX}?agent=agent-alpha")
        body = resp.json()
        for item in body["items"]:
            assert item["triggered_by"] != "agent-alpha"

    async def test_inbox_empty_when_no_external_activity(self, client: AsyncClient):
        await create_hypothesis(client, created_by="agent-alpha")
        resp = await client.get(f"{API_INBOX}?agent=agent-alpha")
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    async def test_inbox_includes_context(self, client: AsyncClient):
        h = await create_hypothesis(client, created_by="agent-alpha", statement="My tracked hypothesis")
        await add_evidence(client, h["id"], created_by="agent-beta")
        resp = await client.get(f"{API_INBOX}?agent=agent-alpha")
        items = resp.json()["items"]
        assert len(items) >= 1
        item = items[0]
        assert "My tracked hypothesis" in item["hypothesis_statement"]
        assert item["event_id"] is not None
        assert item["hypothesis_id"] == h["id"]

    async def test_inbox_since_filter(self, client: AsyncClient):
        h = await create_hypothesis(client, created_by="agent-alpha")
        await add_evidence(client, h["id"], created_by="agent-beta")
        resp = await client.get(f"{API_INBOX}?agent=agent-alpha&since=2099-01-01T00:00:00Z")
        assert resp.json()["total"] == 0

    async def test_inbox_channel_filter(self, client: AsyncClient):
        h1 = await create_hypothesis(client, created_by="agent-alpha", channel="chan-a")
        h2 = await create_hypothesis(client, created_by="agent-alpha", channel="chan-b")
        await add_evidence(client, h1["id"], created_by="agent-beta")
        await add_evidence(client, h2["id"], created_by="agent-beta")
        resp = await client.get(f"{API_INBOX}?agent=agent-alpha&channel=chan-a")
        items = resp.json()["items"]
        for item in items:
            assert item["channel"] == "chan-a"

    async def test_inbox_pagination(self, client: AsyncClient):
        h = await create_hypothesis(client, created_by="agent-alpha")
        for i in range(5):
            await add_evidence(client, h["id"], created_by="agent-beta", content=f"Evidence {i}")
        resp = await client.get(f"{API_INBOX}?agent=agent-alpha&limit=2&offset=0")
        body = resp.json()
        assert len(body["items"]) <= 2
        assert body["has_more"] is True

    async def test_inbox_sorted_most_recent_first(self, client: AsyncClient):
        h = await create_hypothesis(client, created_by="agent-alpha")
        await add_evidence(client, h["id"], created_by="agent-beta", content="First")
        await add_evidence(client, h["id"], created_by="agent-gamma", content="Second")
        resp = await client.get(f"{API_INBOX}?agent=agent-alpha")
        items = resp.json()["items"]
        timestamps = [item["created_at"] for item in items]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_inbox_requires_agent_param(self, client: AsyncClient):
        resp = await client.get(API_INBOX)
        assert resp.status_code == 422

    async def test_inbox_multi_agent_scenario(self, client: AsyncClient):
        """Multiple agents interact; each sees only others' actions on their hypotheses."""
        h_alpha = await create_hypothesis(client, created_by="agent-alpha", statement="Alpha's hyp")
        h_beta = await create_hypothesis(client, created_by="agent-beta", statement="Beta's hyp")
        await add_evidence(client, h_alpha["id"], created_by="agent-beta")
        await add_evidence(client, h_beta["id"], created_by="agent-alpha")

        # Alpha's inbox: should see Beta's action on Alpha's hypothesis
        resp_alpha = await client.get(f"{API_INBOX}?agent=agent-alpha")
        alpha_items = resp_alpha.json()["items"]
        assert any(i["triggered_by"] == "agent-beta" for i in alpha_items)
        assert not any(i["triggered_by"] == "agent-alpha" for i in alpha_items)

        # Beta's inbox: should see Alpha's action on Beta's hypothesis
        resp_beta = await client.get(f"{API_INBOX}?agent=agent-beta")
        beta_items = resp_beta.json()["items"]
        assert any(i["triggered_by"] == "agent-alpha" for i in beta_items)
        assert not any(i["triggered_by"] == "agent-beta" for i in beta_items)
