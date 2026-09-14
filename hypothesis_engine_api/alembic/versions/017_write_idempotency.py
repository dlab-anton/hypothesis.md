"""Atomic replay identities for tenant-scoped create operations.

Revision ID: 017_write_idempotency
Revises: 016_initial_confidence
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "017_write_idempotency"
down_revision = "016_initial_confidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "write_idempotency",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(120), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("tenant_id", "operation", "key", name="uq_write_idempotency_scope"),
    )
    op.create_index("ix_write_idempotency_id", "write_idempotency", ["id"], unique=True)


def downgrade() -> None:
    op.drop_table("write_idempotency")
