# Endpoints Package

from ....schemas.hypothesis import HypothesisRead, EvidenceCounts


def build_hypothesis_read(hypothesis, evidence_counts: dict[str, int]) -> HypothesisRead:
    """Shared helper to build a HypothesisRead from a model + evidence counts."""
    return HypothesisRead(
        id=hypothesis.id,
        statement=hypothesis.statement,
        context=hypothesis.context,
        falsification_criteria=hypothesis.falsification_criteria,
        status=hypothesis.status,
        confidence=hypothesis.confidence,
        initial_confidence=hypothesis.initial_confidence,
        tags=hypothesis.tags or [],
        created_by=hypothesis.created_by,
        parent_id=hypothesis.parent_id,
        is_archived=hypothesis.is_archived,
        evidence_counts=EvidenceCounts(**evidence_counts),
        deadline=hypothesis.deadline,
        metadata=hypothesis.metadata_,
        null_hypothesis=hypothesis.null_hypothesis,
        experimental_design=hypothesis.experimental_design,
        significance_level=hypothesis.significance_level,
        outcome=hypothesis.outcome,
        channel=hypothesis.channel,
        created_at=hypothesis.created_at,
        updated_at=hypothesis.updated_at,
    )
