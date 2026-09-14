"""v2 rebuild - drop old tables, create hypotheses + evidence + events

Revision ID: 001_v2_rebuild
Revises: None
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB


revision: str = "001_v2_rebuild"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old tables (order matters for FK constraints)
    op.drop_table("feedbacks", if_exists=True)
    op.drop_table("hypotheses", if_exists=True)
    op.drop_table("contexts", if_exists=True)
    op.drop_table("observations", if_exists=True)
    op.drop_table("tasks", if_exists=True)
    op.drop_table("workflow_definitions", if_exists=True)

    # Create hypotheses table
    op.create_table(
        "hypotheses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("tags", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("hypotheses.id"), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_hypotheses_status", "hypotheses", ["status"])
    op.create_index("ix_hypotheses_created_by", "hypotheses", ["created_by"])
    op.create_index("ix_hypotheses_tags", "hypotheses", ["tags"], postgresql_using="gin")
    op.create_index("ix_hypotheses_parent_id", "hypotheses", ["parent_id"])
    op.create_index("ix_hypotheses_created_at", "hypotheses", ["created_at"])
    op.create_index("ix_hypotheses_confidence", "hypotheses", ["confidence"])

    # Create evidence table
    op.create_table(
        "evidence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hypothesis_id", UUID(as_uuid=True), sa.ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(500), nullable=True),
        sa.Column("evidence_type", sa.String(20), nullable=False),
        sa.Column("strength", sa.Float(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evidence_hypothesis_id", "evidence", ["hypothesis_id"])
    op.create_index("ix_evidence_type", "evidence", ["evidence_type"])
    op.create_index("ix_evidence_created_at", "evidence", ["created_at"])

    # Create events table
    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hypothesis_id", UUID(as_uuid=True), sa.ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("data", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_events_hypothesis_id", "events", ["hypothesis_id"])
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_created_at", "events", ["created_at"])


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("evidence")
    op.drop_table("hypotheses")
