"""Add channels table.

First-class channel entities with a stated goal. Channels are identified
by name (unique per tenant) and provide mission context for hypotheses
and insights in that channel.

Revision ID: 015_add_channels
Revises: 014_confidence_after
Create Date: 2026-02-26
"""
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "015_add_channels"
down_revision: Union[str, None] = "014_confidence_after"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "tenant_id", name="uq_channels_name_tenant"),
    )
    op.create_index("ix_channels_tenant_id", "channels", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_channels_tenant_id", table_name="channels")
    op.drop_table("channels")
