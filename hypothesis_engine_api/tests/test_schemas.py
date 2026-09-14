"""Unit tests for Pydantic schemas — no database required."""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.hypothesis import (
    HypothesisCreate,
    HypothesisUpdate,
    HypothesisRead,
    HypothesisRevise,
    EvidenceCounts,
)
from app.schemas.evidence import EvidenceCreate, EvidenceRead
from app.schemas.event import EventRead
from app.schemas.insight import InsightCreate, InsightUpdate, InsightRead
from app.schemas.api_key import ApiKeyCreate, ApiKeyGenerated, ApiKeyInfo
from app.core.constants import HypothesisStatus, EvidenceType, InsightType


# ── HypothesisCreate ──────────────────────────────────────────────

class TestHypothesisCreate:
    def test_minimal_valid(self):
        h = HypothesisCreate(statement="Test hypothesis", created_by="tester")
        assert h.statement == "Test hypothesis"
        assert h.created_by == "tester"
        assert h.status == HypothesisStatus.DRAFT
        assert h.confidence is None
        assert h.tags == []
        assert h.context is None
        assert h.falsification_criteria is None
        assert h.deadline is None
        assert h.metadata is None
        assert h.null_hypothesis is None
        assert h.experimental_design is None
        assert h.significance_level is None
        assert h.outcome is None

    def test_full_valid(self):
        dl = datetime(2026, 5, 19, tzinfo=timezone.utc)
        design = {"independent_variable": "Time", "dependent_variable": "Price", "control": "S&P 500"}
        h = HypothesisCreate(
            statement="Connection pool is exhausted",
            context="Prod deploy failed",
            falsification_criteria="If connections are returned normally, this is wrong",
            status="active",
            confidence=0.7,
            tags=["debugging", "database"],
            created_by="claude-code",
            deadline=dl,
            metadata={"component": "db-pool", "deploy_id": "v2.3.1"},
            null_hypothesis="Connection pool is NOT exhausted",
            experimental_design=design,
            significance_level=0.05,
            outcome={"result": "pending"},
        )
        assert h.status == HypothesisStatus.ACTIVE
        assert h.confidence == 0.7
        assert h.tags == ["debugging", "database"]
        assert h.falsification_criteria == "If connections are returned normally, this is wrong"
        assert h.deadline == dl
        assert h.metadata == {"component": "db-pool", "deploy_id": "v2.3.1"}
        assert h.null_hypothesis == "Connection pool is NOT exhausted"
        assert h.experimental_design == design
        assert h.significance_level == 0.05
        assert h.outcome == {"result": "pending"}

    def test_tags_normalized(self):
        h = HypothesisCreate(
            statement="Test", created_by="x", tags=["  Foo ", "BAR", " ", "baz"]
        )
        assert h.tags == ["foo", "bar", "baz"]

    def test_empty_statement_rejected(self):
        with pytest.raises(ValidationError):
            HypothesisCreate(statement="", created_by="tester")

    def test_missing_created_by_rejected(self):
        with pytest.raises(ValidationError):
            HypothesisCreate(statement="Test")

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            HypothesisCreate(statement="T", created_by="x", confidence=-0.1)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValidationError):
            HypothesisCreate(statement="T", created_by="x", confidence=1.1)

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            HypothesisCreate(statement="T", created_by="x", status="invalid_status")

    def test_significance_level_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            HypothesisCreate(statement="T", created_by="x", significance_level=1.5)

    def test_significance_level_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            HypothesisCreate(statement="T", created_by="x", significance_level=-0.1)


# ── HypothesisUpdate ──────────────────────────────────────────────

class TestHypothesisUpdate:
    def test_empty_update_valid(self):
        u = HypothesisUpdate()
        assert u.statement is None
        assert u.status is None

    def test_partial_update(self):
        u = HypothesisUpdate(confidence=0.9)
        assert u.confidence == 0.9
        assert u.statement is None

    def test_tags_normalized_on_update(self):
        u = HypothesisUpdate(tags=["  FOO  "])
        assert u.tags == ["foo"]

    def test_tags_none_valid(self):
        u = HypothesisUpdate(tags=None)
        assert u.tags is None


# ── HypothesisRevise ──────────────────────────────────────────────

class TestHypothesisRevise:
    def test_valid(self):
        r = HypothesisRevise(
            statement="Revised hypothesis",
            rationale="Original hypothesis was too broad based on new evidence",
            created_by="tester",
            confidence=0.5,
        )
        assert r.statement == "Revised hypothesis"
        assert r.rationale == "Original hypothesis was too broad based on new evidence"
        assert r.tags == []
        assert r.falsification_criteria is None
        assert r.null_hypothesis is None
        assert r.experimental_design is None
        assert r.significance_level is None

    def test_with_formal_methodology(self):
        design = {"independent_variable": "Time", "control": "S&P 500"}
        r = HypothesisRevise(
            statement="Revised with formal design",
            rationale="Prior round showed positive trajectory but target missed",
            created_by="tester",
            null_hypothesis="Target will NOT be reached",
            experimental_design=design,
            significance_level=0.05,
        )
        assert r.null_hypothesis == "Target will NOT be reached"
        assert r.experimental_design == design
        assert r.significance_level == 0.05

    def test_with_falsification_criteria(self):
        r = HypothesisRevise(
            statement="Revised hypothesis",
            falsification_criteria="If X happens, this is wrong",
            rationale="Evidence showed the original claim was too narrow",
            created_by="tester",
        )
        assert r.falsification_criteria == "If X happens, this is wrong"

    def test_missing_statement_rejected(self):
        with pytest.raises(ValidationError):
            HypothesisRevise(rationale="Some reason", created_by="tester")

    def test_missing_rationale_rejected(self):
        with pytest.raises(ValidationError):
            HypothesisRevise(statement="Revised", created_by="tester")

    def test_empty_rationale_rejected(self):
        with pytest.raises(ValidationError):
            HypothesisRevise(statement="Revised", rationale="", created_by="tester")


# ── EvidenceCreate ────────────────────────────────────────────────

class TestEvidenceCreate:
    def test_valid_supporting(self):
        e = EvidenceCreate(
            content="Connection count at 20/20",
            evidence_type="supporting",
            created_by="claude-code",
        )
        assert e.evidence_type == EvidenceType.SUPPORTING
        assert e.source is None
        assert e.strength is None
        assert e.confidence is None

    def test_full_valid(self):
        e = EvidenceCreate(
            content="Evidence text",
            source="https://example.com",
            evidence_type="contradicting",
            strength=0.8,
            created_by="researcher",
            confidence=0.3,
        )
        assert e.strength == 0.8
        assert e.confidence == 0.3

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            EvidenceCreate(content="", evidence_type="supporting", created_by="x")

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            EvidenceCreate(content="T", evidence_type="invalid", created_by="x")

    def test_strength_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            EvidenceCreate(content="T", evidence_type="neutral", created_by="x", strength=1.5)


# ── EvidenceRead ──────────────────────────────────────────────────

class TestEvidenceRead:
    def test_from_dict(self):
        now = datetime.now(timezone.utc)
        e = EvidenceRead(
            id=uuid.uuid4(),
            hypothesis_id=uuid.uuid4(),
            content="Test",
            source=None,
            evidence_type="supporting",
            strength=None,
            created_by="x",
            created_at=now,
        )
        assert e.content == "Test"
        assert e.confidence_after is None

    def test_with_confidence_after(self):
        now = datetime.now(timezone.utc)
        e = EvidenceRead(
            id=uuid.uuid4(),
            hypothesis_id=uuid.uuid4(),
            content="Test",
            source=None,
            evidence_type="supporting",
            strength=0.7,
            confidence_after=0.65,
            created_by="x",
            created_at=now,
        )
        assert e.confidence_after == 0.65


# ── HypothesisRead ────────────────────────────────────────────────

class TestHypothesisRead:
    def test_from_dict(self):
        now = datetime.now(timezone.utc)
        h = HypothesisRead(
            id=uuid.uuid4(),
            statement="Test",
            context=None,
            falsification_criteria=None,
            status="draft",
            confidence=None,
            tags=[],
            created_by="x",
            parent_id=None,
            is_archived=False,
            evidence_counts=EvidenceCounts(),
            deadline=None,
            metadata=None,
            null_hypothesis=None,
            experimental_design=None,
            significance_level=None,
            outcome=None,
            channel=None,
            created_at=now,
            updated_at=now,
        )
        assert h.evidence_counts.supporting == 0
        assert h.evidence_counts.contradicting == 0
        assert h.evidence_counts.neutral == 0
        assert h.falsification_criteria is None
        assert h.deadline is None
        assert h.metadata is None
        assert h.null_hypothesis is None
        assert h.experimental_design is None
        assert h.significance_level is None
        assert h.outcome is None

    def test_with_deadline_and_metadata(self):
        now = datetime.now(timezone.utc)
        dl = datetime(2026, 5, 19, tzinfo=timezone.utc)
        h = HypothesisRead(
            id=uuid.uuid4(),
            statement="Test",
            context=None,
            falsification_criteria=None,
            status="draft",
            confidence=None,
            tags=[],
            created_by="x",
            parent_id=None,
            is_archived=False,
            evidence_counts=EvidenceCounts(),
            deadline=dl,
            metadata={"ticker": "ACME", "target_price": 5.0},
            null_hypothesis=None,
            experimental_design=None,
            significance_level=None,
            outcome=None,
            channel=None,
            created_at=now,
            updated_at=now,
        )
        assert h.deadline == dl
        assert h.metadata["ticker"] == "ACME"
        assert h.metadata["target_price"] == 5.0

    def test_with_formal_methodology(self):
        now = datetime.now(timezone.utc)
        design = {"independent_variable": "Time", "dependent_variable": "Price"}
        outcome_data = {"result": "reject_h0", "actual_value": 5.20}
        h = HypothesisRead(
            id=uuid.uuid4(),
            statement="ACME will reach $5",
            context=None,
            falsification_criteria=None,
            status="supported",
            confidence=0.95,
            tags=[],
            created_by="x",
            parent_id=None,
            is_archived=False,
            evidence_counts=EvidenceCounts(),
            deadline=None,
            metadata=None,
            null_hypothesis="ACME will NOT reach $5",
            experimental_design=design,
            significance_level=0.05,
            outcome=outcome_data,
            channel="stock-predictions",
            created_at=now,
            updated_at=now,
        )
        assert h.null_hypothesis == "ACME will NOT reach $5"
        assert h.experimental_design == design
        assert h.significance_level == 0.05
        assert h.outcome["result"] == "reject_h0"


# ── EvidenceCounts ────────────────────────────────────────────────

class TestEvidenceCounts:
    def test_defaults(self):
        c = EvidenceCounts()
        assert c.supporting == 0
        assert c.contradicting == 0
        assert c.neutral == 0


# ── Channel Validation ────────────────────────────────────────────

class TestChannelValidation:
    def test_channel_normalized_lowercase(self):
        h = HypothesisCreate(statement="T", created_by="x", channel="Stock Predictions")
        assert h.channel == "stock-predictions"

    def test_channel_strips_whitespace(self):
        h = HypothesisCreate(statement="T", created_by="x", channel="  debugging  ")
        assert h.channel == "debugging"

    def test_channel_none_valid(self):
        h = HypothesisCreate(statement="T", created_by="x", channel=None)
        assert h.channel is None

    def test_channel_omitted_is_none(self):
        h = HypothesisCreate(statement="T", created_by="x")
        assert h.channel is None

    def test_channel_on_update(self):
        u = HypothesisUpdate(channel="Weather Forecasting")
        assert u.channel == "weather-forecasting"

    def test_channel_on_revise(self):
        r = HypothesisRevise(
            statement="T", rationale="reason", created_by="x",
            channel="Stock Predictions"
        )
        assert r.channel == "stock-predictions"

    def test_channel_too_long_rejected(self):
        with pytest.raises(ValidationError):
            HypothesisCreate(statement="T", created_by="x", channel="a" * 101)


# ── Agent Schemas ────────────────────────────────────────────────

class TestAgentSchemas:
    def test_agent_summary_valid(self):
        from app.schemas.agent import AgentSummary
        s = AgentSummary(
            name="test-agent",
            total_hypotheses=5,
            total_evidence=3,
            total_events=10,
            channels=["debugging", "trading"],
            first_seen=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc),
        )
        assert s.name == "test-agent"
        assert s.total_hypotheses == 5
        assert s.channels == ["debugging", "trading"]

    def test_agent_list_response_valid(self):
        from app.schemas.agent import AgentSummary, AgentListResponse
        now = datetime.now(timezone.utc)
        agents = [
            AgentSummary(name="a", total_hypotheses=1, total_evidence=0, total_events=1,
                         channels=[], first_seen=now, last_active=now),
            AgentSummary(name="b", total_hypotheses=2, total_evidence=1, total_events=3,
                         channels=["ch"], first_seen=now, last_active=now),
        ]
        resp = AgentListResponse(agents=agents, total=2)
        assert resp.total == 2
        assert len(resp.agents) == 2

    def test_inbox_item_valid(self):
        from app.schemas.agent import InboxItem
        item = InboxItem(
            event_id=uuid.uuid4(),
            hypothesis_id=uuid.uuid4(),
            hypothesis_statement="Test hypothesis",
            event_type="evidence_added",
            data={"evidence_type": "supporting"},
            triggered_by="other-agent",
            channel="debugging",
            created_at=datetime.now(timezone.utc),
        )
        assert item.triggered_by == "other-agent"
        assert item.event_type == "evidence_added"
        assert item.channel == "debugging"

    def test_inbox_item_null_channel(self):
        from app.schemas.agent import InboxItem
        item = InboxItem(
            event_id=uuid.uuid4(),
            hypothesis_id=uuid.uuid4(),
            hypothesis_statement="Test",
            event_type="status_changed",
            data={},
            triggered_by="agent-x",
            channel=None,
            created_at=datetime.now(timezone.utc),
        )
        assert item.channel is None

    def test_inbox_response_valid(self):
        from app.schemas.agent import InboxResponse
        resp = InboxResponse(agent="my-agent", items=[], total=0, has_more=False, channel_goals={})
        assert resp.agent == "my-agent"
        assert resp.items == []
        assert resp.has_more is False
        assert resp.channel_goals == {}


# ── Insight Schemas ────────────────────────────────────────────────

class TestInsightSchemas:
    def test_create_minimal(self):
        i = InsightCreate(
            channel="stock-predictions",
            insight_type="calibration",
            content="I'm overconfident on timing predictions",
            created_by="agent-alpha",
        )
        assert i.channel == "stock-predictions"
        assert i.insight_type == InsightType.CALIBRATION
        assert i.metadata is None

    def test_create_full(self):
        i = InsightCreate(
            channel="debugging",
            insight_type="pattern",
            content="7 of 9 refuted hypotheses had no competing hypothesis",
            created_by="agent-alpha",
            metadata={"based_on": ["uuid1", "uuid2"], "sample_size": 9},
        )
        assert i.insight_type == InsightType.PATTERN
        assert i.metadata["sample_size"] == 9

    def test_create_all_types(self):
        for t in ["calibration", "bias", "prior", "pattern"]:
            i = InsightCreate(
                channel="test", insight_type=t, content="Test", created_by="x"
            )
            assert i.insight_type == t

    def test_create_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            InsightCreate(
                channel="test", insight_type="invalid", content="T", created_by="x"
            )

    def test_create_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            InsightCreate(
                channel="test", insight_type="calibration", content="", created_by="x"
            )

    def test_create_empty_channel_rejected(self):
        with pytest.raises(ValidationError):
            InsightCreate(
                channel="", insight_type="calibration", content="T", created_by="x"
            )

    def test_create_missing_created_by_rejected(self):
        with pytest.raises(ValidationError):
            InsightCreate(channel="test", insight_type="calibration", content="T")

    def test_update_partial(self):
        u = InsightUpdate(content="Updated insight", updated_by="agent-beta")
        assert u.content == "Updated insight"
        assert u.metadata is None
        assert u.updated_by == "agent-beta"

    def test_update_metadata_only(self):
        u = InsightUpdate(metadata={"accuracy": 0.45}, updated_by="agent-beta")
        assert u.content is None
        assert u.metadata == {"accuracy": 0.45}

    def test_update_missing_updated_by_rejected(self):
        with pytest.raises(ValidationError):
            InsightUpdate(content="Updated")

    def test_update_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            InsightUpdate(content="", updated_by="x")

    def test_read_from_dict(self):
        now = datetime.now(timezone.utc)
        r = InsightRead(
            id=uuid.uuid4(),
            channel="debugging",
            insight_type="bias",
            content="I overweight momentum",
            created_by="agent-alpha",
            metadata=None,
            created_at=now,
            updated_at=now,
        )
        assert r.insight_type == "bias"
        assert r.channel == "debugging"

    def test_channel_too_long_rejected(self):
        with pytest.raises(ValidationError):
            InsightCreate(
                channel="a" * 101, insight_type="calibration",
                content="T", created_by="x"
            )


# ── ApiKey Schemas ────────────────────────────────────────────────

class TestApiKeySchemas:
    def test_create_empty(self):
        k = ApiKeyCreate()
        assert k.label is None

    def test_create_with_label(self):
        k = ApiKeyCreate(label="my-agent-key")
        assert k.label == "my-agent-key"

    def test_create_label_too_long_rejected(self):
        with pytest.raises(ValidationError):
            ApiKeyCreate(label="a" * 256)

    def test_generated_response(self):
        now = datetime.now(timezone.utc)
        tid = uuid.uuid4()
        g = ApiKeyGenerated(
            key="he_abc123",
            prefix="he_abc123",
            label="test",
            tenant_id=tid,
            created_at=now,
        )
        assert g.key == "he_abc123"
        assert g.prefix == "he_abc123"
        assert g.tenant_id == tid

    def test_info_from_dict(self):
        now = datetime.now(timezone.utc)
        tid = uuid.uuid4()
        info = ApiKeyInfo(
            id=uuid.uuid4(),
            prefix="he_abc123",
            label="my-key",
            tenant_id=tid,
            is_active=True,
            last_used_at=None,
            created_at=now,
        )
        assert info.is_active is True
        assert info.last_used_at is None
        assert info.tenant_id == tid

    def test_info_revoked(self):
        now = datetime.now(timezone.utc)
        info = ApiKeyInfo(
            id=uuid.uuid4(),
            prefix="he_xyz789",
            label=None,
            tenant_id=uuid.uuid4(),
            is_active=False,
            last_used_at=now,
            created_at=now,
        )
        assert info.is_active is False


class TestAuthContext:
    def test_tenant_auth(self):
        from app.core.auth_context import AuthContext
        tid = uuid.uuid4()
        ctx = AuthContext(tenant_id=tid, is_master=False)
        assert ctx.tenant_id == tid
        assert ctx.is_master is False

    def test_master_auth(self):
        from app.core.auth_context import AuthContext
        ctx = AuthContext(tenant_id=None, is_master=True)
        assert ctx.tenant_id is None
        assert ctx.is_master is True

    def test_frozen(self):
        from app.core.auth_context import AuthContext
        ctx = AuthContext(tenant_id=uuid.uuid4(), is_master=False)
        with pytest.raises(AttributeError):
            ctx.tenant_id = uuid.uuid4()

    def test_api_key_create_with_tenant_id(self):
        tid = uuid.uuid4()
        k = ApiKeyCreate(tenant_id=tid)
        assert k.tenant_id == tid

    def test_api_key_create_without_tenant_id(self):
        k = ApiKeyCreate()
        assert k.tenant_id is None


# ── Security Hardening Validators ─────────────────────────────────

class TestCreatedByValidation:
    """Verify created_by rejects XSS / injection characters."""

    def test_valid_simple_name(self):
        h = HypothesisCreate(statement="T", created_by="agent-alpha")
        assert h.created_by == "agent-alpha"

    def test_valid_email_style(self):
        h = HypothesisCreate(statement="T", created_by="user@example.com")
        assert h.created_by == "user@example.com"

    def test_valid_with_dots_and_spaces(self):
        h = HypothesisCreate(statement="T", created_by="Dr. Agent Beta")
        assert h.created_by == "Dr. Agent Beta"

    def test_strips_whitespace(self):
        h = HypothesisCreate(statement="T", created_by="  agent  ")
        assert h.created_by == "agent"

    def test_rejects_script_tags(self):
        with pytest.raises(ValidationError, match="created_by"):
            HypothesisCreate(statement="T", created_by="<script>alert(1)</script>")

    def test_rejects_semicolons(self):
        with pytest.raises(ValidationError, match="created_by"):
            HypothesisCreate(statement="T", created_by="agent; DROP TABLE")

    def test_rejects_slashes(self):
        with pytest.raises(ValidationError, match="created_by"):
            HypothesisCreate(statement="T", created_by="../../etc/passwd")

    def test_rejects_quotes(self):
        with pytest.raises(ValidationError, match="created_by"):
            HypothesisCreate(statement="T", created_by='agent"OR 1=1')

    def test_evidence_created_by_validated(self):
        with pytest.raises(ValidationError, match="created_by"):
            EvidenceCreate(
                content="Test", evidence_type="supporting",
                created_by="<script>alert(1)</script>",
            )

    def test_insight_created_by_validated(self):
        with pytest.raises(ValidationError, match="created_by"):
            InsightCreate(
                channel="test", insight_type="calibration",
                content="Test", created_by="agent;drop",
            )

    def test_hypothesis_update_created_by_validated(self):
        with pytest.raises(ValidationError, match="created_by"):
            HypothesisUpdate(created_by="<img src=x>")

    def test_revise_created_by_validated(self):
        with pytest.raises(ValidationError, match="created_by"):
            HypothesisRevise(
                statement="T", rationale="reason",
                created_by="agent<>evil",
            )


class TestJsonSizeValidation:
    """Verify JSON dict fields reject payloads over 64KB."""

    def test_small_metadata_accepted(self):
        h = HypothesisCreate(
            statement="T", created_by="x",
            metadata={"key": "value"},
        )
        assert h.metadata == {"key": "value"}

    def test_large_metadata_rejected(self):
        big = {"data": "x" * 70000}
        with pytest.raises(ValidationError, match="64KB"):
            HypothesisCreate(statement="T", created_by="x", metadata=big)

    def test_large_experimental_design_rejected(self):
        big = {"plan": "y" * 70000}
        with pytest.raises(ValidationError, match="64KB"):
            HypothesisCreate(statement="T", created_by="x", experimental_design=big)

    def test_large_outcome_rejected(self):
        big = {"result": "z" * 70000}
        with pytest.raises(ValidationError, match="64KB"):
            HypothesisCreate(statement="T", created_by="x", outcome=big)

    def test_update_large_metadata_rejected(self):
        big = {"data": "x" * 70000}
        with pytest.raises(ValidationError, match="64KB"):
            HypothesisUpdate(metadata=big)

    def test_insight_large_metadata_rejected(self):
        big = {"data": "x" * 70000}
        with pytest.raises(ValidationError, match="64KB"):
            InsightCreate(
                channel="test", insight_type="calibration",
                content="T", created_by="x", metadata=big,
            )


class TestTagsBoundsValidation:
    """Verify tags list enforces max count and per-tag length."""

    def test_tags_within_limit_accepted(self):
        tags = [f"tag-{i}" for i in range(50)]
        h = HypothesisCreate(statement="T", created_by="x", tags=tags)
        assert len(h.tags) == 50

    def test_tags_over_limit_rejected(self):
        tags = [f"tag-{i}" for i in range(51)]
        with pytest.raises(ValidationError, match="50 tags"):
            HypothesisCreate(statement="T", created_by="x", tags=tags)

    def test_long_tag_truncated(self):
        long_tag = "a" * 150
        h = HypothesisCreate(statement="T", created_by="x", tags=[long_tag])
        assert len(h.tags[0]) == 100

    def test_update_tags_over_limit_rejected(self):
        tags = [f"tag-{i}" for i in range(51)]
        with pytest.raises(ValidationError, match="50 tags"):
            HypothesisUpdate(tags=tags)

    def test_revise_tags_over_limit_rejected(self):
        tags = [f"tag-{i}" for i in range(51)]
        with pytest.raises(ValidationError, match="50 tags"):
            HypothesisRevise(statement="T", rationale="r", created_by="x", tags=tags)


class TestInsightContentMaxLength:
    """Verify insight content enforces max length."""

    def test_content_at_limit_accepted(self):
        i = InsightCreate(
            channel="test", insight_type="calibration",
            content="x" * 10000, created_by="x",
        )
        assert len(i.content) == 10000

    def test_content_over_limit_rejected(self):
        with pytest.raises(ValidationError):
            InsightCreate(
                channel="test", insight_type="calibration",
                content="x" * 10001, created_by="x",
            )

    def test_update_content_over_limit_rejected(self):
        with pytest.raises(ValidationError):
            InsightUpdate(content="x" * 10001, updated_by="x")


class TestApiKeyLabelValidation:
    """Verify API key label rejects injection characters."""

    def test_valid_label(self):
        k = ApiKeyCreate(label="my-agent-key")
        assert k.label == "my-agent-key"

    def test_label_strips_whitespace(self):
        k = ApiKeyCreate(label="  my key  ")
        assert k.label == "my key"

    def test_label_rejects_script(self):
        with pytest.raises(ValidationError, match="label"):
            ApiKeyCreate(label="<script>alert(1)</script>")


class TestCreationStatusValidation:
    """Verify hypotheses can only be created in draft or active status."""

    def test_default_draft_accepted(self):
        h = HypothesisCreate(statement="T", created_by="x")
        assert h.status == "draft"

    def test_explicit_draft_accepted(self):
        h = HypothesisCreate(statement="T", created_by="x", status="draft")
        assert h.status == "draft"

    def test_active_accepted(self):
        h = HypothesisCreate(statement="T", created_by="x", status="active")
        assert h.status == "active"

    def test_testing_rejected(self):
        with pytest.raises(ValidationError, match="draft.*active"):
            HypothesisCreate(statement="T", created_by="x", status="testing")

    def test_supported_rejected(self):
        with pytest.raises(ValidationError, match="draft.*active"):
            HypothesisCreate(statement="T", created_by="x", status="supported")

    def test_refuted_rejected(self):
        with pytest.raises(ValidationError, match="draft.*active"):
            HypothesisCreate(statement="T", created_by="x", status="refuted")

    def test_inconclusive_rejected(self):
        with pytest.raises(ValidationError, match="draft.*active"):
            HypothesisCreate(statement="T", created_by="x", status="inconclusive")

    def test_revised_rejected(self):
        with pytest.raises(ValidationError, match="draft.*active"):
            HypothesisCreate(statement="T", created_by="x", status="revised")

    def test_archived_rejected(self):
        with pytest.raises(ValidationError, match="draft.*active"):
            HypothesisCreate(statement="T", created_by="x", status="archived")
