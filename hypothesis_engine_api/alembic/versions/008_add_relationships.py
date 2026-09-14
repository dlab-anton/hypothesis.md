"""Add relationships table for hypothesis hierarchy, competition, and dependency.

Revision ID: 008_relationships
Revises: 007_agent_indexes
Create Date: 2026-02-21
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "008_relationships"
down_revision: Union[str, None] = "007_agent_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "relationships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_hypothesis_id", UUID(as_uuid=True), sa.ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_hypothesis_id", UUID(as_uuid=True), sa.ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(30), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_relationships_source", "relationships", ["source_hypothesis_id"])
    op.create_index("ix_relationships_target", "relationships", ["target_hypothesis_id"])
    op.create_unique_constraint(
        "uq_relationships_source_target_type",
        "relationships",
        ["source_hypothesis_id", "target_hypothesis_id", "relationship_type"],
    )


def downgrade() -> None:
    op.drop_table("relationships")
