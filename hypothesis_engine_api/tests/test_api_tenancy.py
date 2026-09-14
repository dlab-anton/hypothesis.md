"""Cross-tenant isolation tests.

Two tenants, each with their own client fixture. Verifies that:
- Tenant A cannot see Tenant B's hypotheses, evidence, or events
- Master key can see data from all tenants
- Create operations stamp the correct tenant_id
"""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext
from app.api.deps import get_db_session
from app.core.security import get_api_key
from app.main import app

TENANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

BASE = "/api/v1"


@pytest.fixture
async def workspace_clients(db_session: AsyncSession):
    """Use real hashed keys; shared global auth overrides cannot represent two tenants."""
    from app.crud.crud_api_key import create_api_key
    from app.core.config import settings

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides.pop(get_api_key, None)
    clients = []
    try:
        for tenant in (TENANT_A, TENANT_B):
            model, raw_key = await create_api_key(db_session)
            model.tenant_id = tenant
            await db_session.flush()
            clients.append(AsyncClient(transport=ASGITransport(app=app),
                base_url="http://test", headers={"X-API-Key": raw_key}))
        clients.append(AsyncClient(transport=ASGITransport(app=app),
            base_url="http://test", headers={"X-API-Key": settings.API_MASTER_KEY}))
        yield clients
    finally:
        for client in clients:
            await client.aclose()
        app.dependency_overrides.clear()


@pytest.fixture
async def client_a(workspace_clients):
    return workspace_clients[0]


@pytest.fixture
async def client_b(workspace_clients):
    return workspace_clients[1]


@pytest.fixture
async def master_client(workspace_clients):
    return workspace_clients[2]


def _hyp(statement: str, **kwargs) -> dict:
    """Helper to build a hypothesis payload."""
    return {"statement": statement, "created_by": "test-agent", **kwargs}


# ── Hypothesis isolation ──────────────────────────────────────────


class TestHypothesisIsolation:
    async def test_tenant_a_cannot_see_tenant_b_hypotheses(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        # A creates a hypothesis
        resp = await client_a.post(f"{BASE}/hypotheses", json=_hyp("Tenant A hypothesis"))
        assert resp.status_code == 201
        h_id = resp.json()["id"]

        # B cannot see it
        resp = await client_b.get(f"{BASE}/hypotheses/{h_id}")
        assert resp.status_code == 404

        # B's list is empty
        resp = await client_b.get(f"{BASE}/hypotheses")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_tenant_b_cannot_see_tenant_a_hypotheses(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        # B creates a hypothesis
        resp = await client_b.post(f"{BASE}/hypotheses", json=_hyp("Tenant B hypothesis"))
        assert resp.status_code == 201
        h_id = resp.json()["id"]

        # A cannot see it
        resp = await client_a.get(f"{BASE}/hypotheses/{h_id}")
        assert resp.status_code == 404

    async def test_tenant_a_cannot_update_tenant_b_hypothesis(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        resp = await client_b.post(f"{BASE}/hypotheses", json=_hyp("B's hypothesis"))
        h_id = resp.json()["id"]

        resp = await client_a.patch(
            f"{BASE}/hypotheses/{h_id}",
            json={"confidence": 0.9, "created_by": "attacker"},
        )
        assert resp.status_code == 404

    async def test_tenant_a_cannot_archive_tenant_b_hypothesis(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        resp = await client_b.post(f"{BASE}/hypotheses", json=_hyp("B's to archive"))
        h_id = resp.json()["id"]

        resp = await client_a.delete(f"{BASE}/hypotheses/{h_id}")
        assert resp.status_code == 404

    async def test_list_only_shows_own_tenant(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        await client_a.post(f"{BASE}/hypotheses", json=_hyp("A-1"))
        await client_a.post(f"{BASE}/hypotheses", json=_hyp("A-2"))
        await client_b.post(f"{BASE}/hypotheses", json=_hyp("B-1"))

        resp_a = await client_a.get(f"{BASE}/hypotheses")
        resp_b = await client_b.get(f"{BASE}/hypotheses")

        assert resp_a.json()["total"] == 2
        assert resp_b.json()["total"] == 1


# ── Evidence isolation ────────────────────────────────────────────


class TestEvidenceIsolation:
    async def test_tenant_a_cannot_add_evidence_to_tenant_b(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        resp = await client_b.post(f"{BASE}/hypotheses", json=_hyp("B's hypothesis"))
        h_id = resp.json()["id"]

        resp = await client_a.post(
            f"{BASE}/hypotheses/{h_id}/evidence",
            json={"content": "sneaky evidence", "created_by": "attacker", "evidence_type": "neutral"},
        )
        assert resp.status_code == 404

    async def test_tenant_a_cannot_list_evidence_on_tenant_b(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        resp = await client_b.post(f"{BASE}/hypotheses", json=_hyp("B's hypothesis"))
        h_id = resp.json()["id"]

        # Add evidence as B
        await client_b.post(
            f"{BASE}/hypotheses/{h_id}/evidence",
            json={"content": "B's evidence", "created_by": "b-agent"},
        )

        # A can't see it
        resp = await client_a.get(f"{BASE}/hypotheses/{h_id}/evidence")
        assert resp.status_code == 404


# ── Timeline isolation ────────────────────────────────────────────


class TestTimelineIsolation:
    async def test_tenant_a_cannot_see_tenant_b_timeline(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        resp = await client_b.post(f"{BASE}/hypotheses", json=_hyp("B's hypothesis"))
        h_id = resp.json()["id"]

        resp = await client_a.get(f"{BASE}/hypotheses/{h_id}/timeline")
        assert resp.status_code == 404

    async def test_tenant_a_cannot_see_tenant_b_lineage(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        resp = await client_b.post(f"{BASE}/hypotheses", json=_hyp("B's hypothesis"))
        h_id = resp.json()["id"]

        resp = await client_a.get(f"{BASE}/hypotheses/{h_id}/lineage")
        assert resp.status_code == 404

    async def test_tenant_a_cannot_revise_tenant_b_hypothesis(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        # B creates and moves to supported (needs to go through active → testing → supported first)
        resp = await client_b.post(f"{BASE}/hypotheses", json=_hyp("B's to revise"))
        h_id = resp.json()["id"]
        await client_b.patch(f"{BASE}/hypotheses/{h_id}", json={"status": "active", "created_by": "b"})
        await client_b.patch(f"{BASE}/hypotheses/{h_id}", json={"status": "testing", "created_by": "b"})
        await client_b.patch(f"{BASE}/hypotheses/{h_id}", json={"status": "supported", "created_by": "b"})

        resp = await client_a.post(
            f"{BASE}/hypotheses/{h_id}/revise",
            json={"statement": "Revised by attacker", "rationale": "hostile takeover", "created_by": "attacker"},
        )
        assert resp.status_code == 404


# ── Stats isolation ───────────────────────────────────────────────


class TestStatsIsolation:
    async def test_stats_scoped_to_tenant(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        await client_a.post(f"{BASE}/hypotheses", json=_hyp("A-1"))
        await client_a.post(f"{BASE}/hypotheses", json=_hyp("A-2"))
        await client_a.post(f"{BASE}/hypotheses", json=_hyp("A-3"))
        await client_b.post(f"{BASE}/hypotheses", json=_hyp("B-1"))

        resp_a = await client_a.get(f"{BASE}/hypotheses/stats")
        resp_b = await client_b.get(f"{BASE}/hypotheses/stats")

        assert resp_a.json()["total"] == 3
        assert resp_b.json()["total"] == 1


# ── Master key override ──────────────────────────────────────────


class TestMasterKeyOverride:
    async def test_master_sees_all_tenants(
        self, client_a: AsyncClient, client_b: AsyncClient, master_client: AsyncClient,
    ):
        await client_a.post(f"{BASE}/hypotheses", json=_hyp("A"))
        await client_b.post(f"{BASE}/hypotheses", json=_hyp("B"))

        resp = await master_client.get(f"{BASE}/hypotheses")
        assert resp.json()["total"] >= 2

    async def test_master_sees_specific_hypothesis_from_any_tenant(
        self, client_a: AsyncClient, master_client: AsyncClient,
    ):
        resp = await client_a.post(f"{BASE}/hypotheses", json=_hyp("A's hypothesis"))
        h_id = resp.json()["id"]

        resp = await master_client.get(f"{BASE}/hypotheses/{h_id}")
        assert resp.status_code == 200
        assert resp.json()["statement"] == "A's hypothesis"


# ── Agent endpoint isolation ──────────────────────────────────────


class TestAgentIsolation:
    async def test_agents_list_scoped_to_tenant(
        self, client_a: AsyncClient, client_b: AsyncClient,
    ):
        await client_a.post(f"{BASE}/hypotheses", json=_hyp("A", created_by="agent-alpha"))
        await client_b.post(f"{BASE}/hypotheses", json=_hyp("B", created_by="agent-beta"))

        resp_a = await client_a.get(f"{BASE}/agents")
        names_a = [a["name"] for a in resp_a.json()["agents"]]
        assert "agent-alpha" in names_a
        assert "agent-beta" not in names_a

        resp_b = await client_b.get(f"{BASE}/agents")
        names_b = [a["name"] for a in resp_b.json()["agents"]]
        assert "agent-beta" in names_b
        assert "agent-alpha" not in names_b
