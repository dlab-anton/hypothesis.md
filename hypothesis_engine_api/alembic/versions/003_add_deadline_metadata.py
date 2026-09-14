"""Add deadline and metadata columns to hypotheses

Revision ID: 003_deadline_metadata
Revises: 002_falsification_criteria
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "003_deadline_metadata"
down_revision: Union[str, None] = "002_falsification_criteria"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hypotheses", sa.Column("deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hypotheses", sa.Column("metadata", JSONB(), nullable=True))
    op.create_index("ix_hypotheses_deadline", "hypotheses", ["deadline"])


def downgrade() -> None:
    op.drop_index("ix_hypotheses_deadline", table_name="hypotheses")
    op.drop_column("hypotheses", "metadata")
    op.drop_column("hypotheses", "deadline")
