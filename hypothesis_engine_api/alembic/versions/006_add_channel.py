"""Add channel column to hypotheses

Revision ID: 006_add_channel
Revises: 004_formal_methodology
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006_add_channel"
down_revision: Union[str, None] = "004_formal_methodology"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hypotheses", sa.Column("channel", sa.String(100), nullable=True))
    op.create_index("ix_hypotheses_channel", "hypotheses", ["channel"])


def downgrade() -> None:
    op.drop_index("ix_hypotheses_channel", table_name="hypotheses")
    op.drop_column("hypotheses", "channel")
