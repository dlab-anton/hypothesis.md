"""Add tenant_id to api_keys, hypotheses, insights, relationships.

Revision ID: 011_tenant_id
Revises: 010_api_keys
Create Date: 2026-02-21
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "011_tenant_id"
down_revision: Union[str, None] = "010_api_keys"
branch_labels = None
depends_on = None

# Default tenant for existing data
DEFAULT_TENANT = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # Phase A: Add nullable columns
    for table in ["api_keys", "hypotheses", "insights", "relationships"]:
        op.add_column(table, sa.Column("tenant_id", UUID(as_uuid=True), nullable=True))
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])

    # Phase B: Backfill existing rows with default tenant
    for table in ["api_keys", "hypotheses", "insights", "relationships"]:
        op.execute(f"UPDATE {table} SET tenant_id = '{DEFAULT_TENANT}' WHERE tenant_id IS NULL")

    # Phase C: Make NOT NULL
    for table in ["api_keys", "hypotheses", "insights", "relationships"]:
        op.alter_column(table, "tenant_id", nullable=False)


def downgrade() -> None:
    for table in ["api_keys", "hypotheses", "insights", "relationships"]:
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")
