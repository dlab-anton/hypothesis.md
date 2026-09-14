"""Add insights table for channel-scoped domain knowledge.

Revision ID: 009_insights
Revises: 008_relationships
Create Date: 2026-02-21
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "009_insights"
down_revision: Union[str, None] = "008_relationships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "insights",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel", sa.String(100), nullable=False),
        sa.Column("insight_type", sa.String(30), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_insights_channel", "insights", ["channel"])
    op.create_index("ix_insights_channel_type", "insights", ["channel", "insight_type"])


def downgrade() -> None:
    op.drop_table("insights")
