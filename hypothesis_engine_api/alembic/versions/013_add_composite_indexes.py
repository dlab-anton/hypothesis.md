"""Add composite indexes for common query patterns.

Adds composite indexes on (status, tenant_id), (created_by, tenant_id),
and (source_hypothesis_id, target_hypothesis_id) to improve query performance
for filtered list endpoints and relationship lookups.

Revision ID: 013_composite_indexes
Revises: 012_enum_checks
Create Date: 2026-02-25
"""
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013_composite_indexes"
down_revision: Union[str, None] = "012_enum_checks"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Hypotheses: most list queries filter by status + tenant_id
    op.create_index(
        "ix_hypotheses_status_tenant",
        "hypotheses",
        ["status", "tenant_id"],
    )
    # Hypotheses: agent activity queries filter by created_by + tenant_id
    op.create_index(
        "ix_hypotheses_created_by_tenant",
        "hypotheses",
        ["created_by", "tenant_id"],
    )
    # Relationships: bidirectional lookups need both columns together
    op.create_index(
        "ix_relationships_source_target",
        "relationships",
        ["source_hypothesis_id", "target_hypothesis_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_relationships_source_target", table_name="relationships")
    op.drop_index("ix_hypotheses_created_by_tenant", table_name="hypotheses")
    op.drop_index("ix_hypotheses_status_tenant", table_name="hypotheses")
