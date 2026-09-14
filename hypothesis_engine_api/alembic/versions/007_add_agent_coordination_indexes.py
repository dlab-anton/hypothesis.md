"""Add indexes on created_by for agent coordination endpoints

Revision ID: 007_agent_indexes
Revises: 006_add_channel
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op


revision: str = "007_agent_indexes"
down_revision: Union[str, None] = "006_add_channel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_evidence_created_by", "evidence", ["created_by"])
    op.create_index("ix_events_created_by", "events", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_events_created_by", table_name="events")
    op.drop_index("ix_evidence_created_by", table_name="evidence")
