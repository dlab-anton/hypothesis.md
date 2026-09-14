from enum import StrEnum


class HypothesisStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    TESTING = "testing"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"
    REVISED = "revised"
    ARCHIVED = "archived"


class EvidenceType(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    NEUTRAL = "neutral"


class EventType(StrEnum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    CONFIDENCE_CHANGED = "confidence_changed"
    CONFIDENCE_CONTRADICTION_WARNING = "confidence_contradiction_warning"
    EVIDENCE_ADDED = "evidence_added"
    REVISED = "revised"
    ARCHIVED = "archived"
    UNARCHIVED = "unarchived"
    # Relationship lifecycle
    RELATIONSHIP_CREATED = "relationship_created"
    RELATIONSHIP_REMOVED = "relationship_removed"
    # Propagated signals on related hypotheses
    CHILD_EVIDENCE_ADDED = "child_evidence_added"
    CHILD_STATUS_CHANGED = "child_status_changed"
    COMPETING_EVIDENCE_ADDED = "competing_evidence_added"
    COMPETING_STATUS_CHANGED = "competing_status_changed"
    DEPENDENCY_EVIDENCE_ADDED = "dependency_evidence_added"
    DEPENDENCY_STATUS_CHANGED = "dependency_status_changed"


class RelationshipType(StrEnum):
    DECOMPOSES_INTO = "decomposes_into"
    COMPETES_WITH = "competes_with"
    DEPENDS_ON = "depends_on"


class InsightType(StrEnum):
    CALIBRATION = "calibration"
    BIAS = "bias"
    PRIOR = "prior"
    PATTERN = "pattern"


# Symmetric relationship types — direction doesn't matter, so H1→H2 == H2→H1
SYMMETRIC_RELATIONSHIP_TYPES = {RelationshipType.COMPETES_WITH}


# Valid status transitions: {current_status: [allowed_next_statuses]}
# NOTE: active can ONLY go to testing (not directly to supported/refuted/inconclusive).
# This enforces the discipline of actually testing before concluding.
VALID_TRANSITIONS: dict[HypothesisStatus, list[HypothesisStatus]] = {
    HypothesisStatus.DRAFT: [HypothesisStatus.ACTIVE, HypothesisStatus.ARCHIVED],
    HypothesisStatus.ACTIVE: [
        HypothesisStatus.TESTING,
        HypothesisStatus.ARCHIVED,
    ],
    HypothesisStatus.TESTING: [
        HypothesisStatus.SUPPORTED,
        HypothesisStatus.REFUTED,
        HypothesisStatus.INCONCLUSIVE,
        HypothesisStatus.ACTIVE,
        HypothesisStatus.ARCHIVED,
    ],
    HypothesisStatus.SUPPORTED: [
        HypothesisStatus.REVISED,
        HypothesisStatus.ARCHIVED,
    ],
    HypothesisStatus.REFUTED: [
        HypothesisStatus.REVISED,
        HypothesisStatus.ARCHIVED,
    ],
    HypothesisStatus.INCONCLUSIVE: [
        HypothesisStatus.ACTIVE,
        HypothesisStatus.REVISED,
        HypothesisStatus.ARCHIVED,
    ],
    HypothesisStatus.REVISED: [],  # Terminal
    HypothesisStatus.ARCHIVED: [HypothesisStatus.ACTIVE],  # Unarchive
}
