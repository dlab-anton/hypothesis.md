"""Add formal scientific methodology fields: null_hypothesis, experimental_design, significance_level, outcome

Revision ID: 004_formal_methodology
Revises: 003_deadline_metadata
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "004_formal_methodology"
down_revision: Union[str, None] = "003_deadline_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hypotheses", sa.Column("null_hypothesis", sa.Text(), nullable=True))
    op.add_column("hypotheses", sa.Column("experimental_design", JSONB(), nullable=True))
    op.add_column("hypotheses", sa.Column("significance_level", sa.Float(), nullable=True))
    op.add_column("hypotheses", sa.Column("outcome", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("hypotheses", "outcome")
    op.drop_column("hypotheses", "significance_level")
    op.drop_column("hypotheses", "experimental_design")
    op.drop_column("hypotheses", "null_hypothesis")
