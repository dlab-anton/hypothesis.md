"""Add CHECK constraints for string-typed enum columns.

Enforces valid values at the database level for evidence_type, event_type,
relationship_type, hypothesis status, and insight_type.

Revision ID: 012_enum_checks
Revises: 011_tenant_id
Create Date: 2026-02-25
"""
from typing import Union

from alembic import op

revision: str = "012_enum_checks"
down_revision: Union[str, None] = "011_tenant_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_evidence_type",
        "evidence",
        "evidence_type IN ('supporting', 'contradicting', 'neutral')",
    )
    op.create_check_constraint(
        "ck_event_type",
        "events",
        "event_type IN ("
        "'created', 'status_changed', 'confidence_changed', "
        "'confidence_contradiction_warning', 'evidence_added', "
        "'revised', 'archived', 'unarchived', "
        "'relationship_created', 'relationship_removed', "
        "'child_evidence_added', 'child_status_changed', "
        "'competing_evidence_added', 'competing_status_changed', "
        "'dependency_evidence_added', 'dependency_status_changed'"
        ")",
    )
    op.create_check_constraint(
        "ck_relationship_type",
        "relationships",
        "relationship_type IN ('decomposes_into', 'competes_with', 'depends_on')",
    )
    op.create_check_constraint(
        "ck_hypothesis_status",
        "hypotheses",
        "status IN ('draft', 'active', 'testing', 'supported', 'refuted', "
        "'inconclusive', 'revised', 'archived')",
    )
    op.create_check_constraint(
        "ck_insight_type",
        "insights",
        "insight_type IN ('calibration', 'bias', 'prior', 'pattern')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_insight_type", "insights", type_="check")
    op.drop_constraint("ck_hypothesis_status", "hypotheses", type_="check")
    op.drop_constraint("ck_relationship_type", "relationships", type_="check")
    op.drop_constraint("ck_event_type", "events", type_="check")
    op.drop_constraint("ck_evidence_type", "evidence", type_="check")
