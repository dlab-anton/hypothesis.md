"""Unit tests for constants and status transition logic — no database required."""

from app.core.constants import (
    HypothesisStatus,
    EvidenceType,
    EventType,
    RelationshipType,
    InsightType,
    SYMMETRIC_RELATIONSHIP_TYPES,
    VALID_TRANSITIONS,
)


class TestHypothesisStatus:
    def test_all_values(self):
        expected = {"draft", "active", "testing", "supported", "refuted", "inconclusive", "revised", "archived"}
        assert {s.value for s in HypothesisStatus} == expected

    def test_str_enum(self):
        assert str(HypothesisStatus.DRAFT) == "draft"
        assert HypothesisStatus("active") == HypothesisStatus.ACTIVE


class TestEvidenceType:
    def test_all_values(self):
        assert {e.value for e in EvidenceType} == {"supporting", "contradicting", "neutral"}


class TestEventType:
    def test_all_values(self):
        expected = {
            "created", "status_changed", "confidence_changed",
            "confidence_contradiction_warning", "evidence_added",
            "revised", "archived", "unarchived",
            # Relationship events
            "relationship_created", "relationship_removed",
            # Propagated signals
            "child_evidence_added", "child_status_changed",
            "competing_evidence_added", "competing_status_changed",
            "dependency_evidence_added", "dependency_status_changed",
        }
        assert {e.value for e in EventType} == expected


class TestRelationshipType:
    def test_all_values(self):
        expected = {"decomposes_into", "competes_with", "depends_on"}
        assert {r.value for r in RelationshipType} == expected

    def test_str_enum(self):
        assert str(RelationshipType.DECOMPOSES_INTO) == "decomposes_into"
        assert RelationshipType("competes_with") == RelationshipType.COMPETES_WITH

    def test_symmetric_types(self):
        assert RelationshipType.COMPETES_WITH in SYMMETRIC_RELATIONSHIP_TYPES
        assert RelationshipType.DECOMPOSES_INTO not in SYMMETRIC_RELATIONSHIP_TYPES
        assert RelationshipType.DEPENDS_ON not in SYMMETRIC_RELATIONSHIP_TYPES


class TestInsightType:
    def test_all_values(self):
        expected = {"calibration", "bias", "prior", "pattern"}
        assert {i.value for i in InsightType} == expected

    def test_str_enum(self):
        assert str(InsightType.CALIBRATION) == "calibration"
        assert InsightType("bias") == InsightType.BIAS


class TestValidTransitions:
    def test_draft_transitions(self):
        allowed = VALID_TRANSITIONS[HypothesisStatus.DRAFT]
        assert HypothesisStatus.ACTIVE in allowed
        assert HypothesisStatus.ARCHIVED in allowed
        assert HypothesisStatus.TESTING not in allowed

    def test_active_transitions(self):
        allowed = VALID_TRANSITIONS[HypothesisStatus.ACTIVE]
        assert HypothesisStatus.TESTING in allowed
        assert HypothesisStatus.ARCHIVED in allowed
        # Cannot skip testing — must go through testing before concluding
        assert HypothesisStatus.SUPPORTED not in allowed
        assert HypothesisStatus.REFUTED not in allowed
        assert HypothesisStatus.INCONCLUSIVE not in allowed
        assert HypothesisStatus.DRAFT not in allowed

    def test_testing_transitions(self):
        allowed = VALID_TRANSITIONS[HypothesisStatus.TESTING]
        assert HypothesisStatus.SUPPORTED in allowed
        assert HypothesisStatus.REFUTED in allowed
        assert HypothesisStatus.INCONCLUSIVE in allowed
        assert HypothesisStatus.ACTIVE in allowed
        assert HypothesisStatus.ARCHIVED in allowed

    def test_supported_transitions(self):
        allowed = VALID_TRANSITIONS[HypothesisStatus.SUPPORTED]
        assert HypothesisStatus.REVISED in allowed
        assert HypothesisStatus.ARCHIVED in allowed
        assert len(allowed) == 2

    def test_refuted_transitions(self):
        allowed = VALID_TRANSITIONS[HypothesisStatus.REFUTED]
        assert HypothesisStatus.REVISED in allowed
        assert HypothesisStatus.ARCHIVED in allowed
        assert len(allowed) == 2

    def test_inconclusive_transitions(self):
        allowed = VALID_TRANSITIONS[HypothesisStatus.INCONCLUSIVE]
        assert HypothesisStatus.ACTIVE in allowed
        assert HypothesisStatus.REVISED in allowed
        assert HypothesisStatus.ARCHIVED in allowed

    def test_revised_is_terminal(self):
        assert VALID_TRANSITIONS[HypothesisStatus.REVISED] == []

    def test_archived_can_unarchive(self):
        allowed = VALID_TRANSITIONS[HypothesisStatus.ARCHIVED]
        assert HypothesisStatus.ACTIVE in allowed
        assert len(allowed) == 1

    def test_all_statuses_have_transition_entry(self):
        for status in HypothesisStatus:
            assert status in VALID_TRANSITIONS, f"Missing transition entry for {status}"


class TestApiKeyCrud:
    """Unit tests for the key generation/hashing helpers (no DB needed)."""

    def test_generate_key_has_prefix(self):
        from app.crud.crud_api_key import generate_key
        key = generate_key()
        assert key.startswith("he_")
        assert len(key) > 10

    def test_generate_key_unique(self):
        from app.crud.crud_api_key import generate_key
        keys = {generate_key() for _ in range(20)}
        assert len(keys) == 20

    def test_hash_key_deterministic(self):
        from app.crud.crud_api_key import hash_key
        h1 = hash_key("he_test123")
        h2 = hash_key("he_test123")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_key_different_inputs(self):
        from app.crud.crud_api_key import hash_key
        assert hash_key("he_aaa") != hash_key("he_bbb")

    def test_extract_prefix(self):
        from app.crud.crud_api_key import extract_prefix
        assert extract_prefix("he_abcdefghijk") == "he_abcdefg"
        assert len(extract_prefix("he_abcdefghijk")) == 10
