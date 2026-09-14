"""Add falsification_criteria column, widen event_type column

Revision ID: 002_falsification_criteria
Revises: 001_v2_rebuild
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_falsification_criteria"
down_revision: Union[str, None] = "001_v2_rebuild"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hypotheses", sa.Column("falsification_criteria", sa.Text(), nullable=True))
    op.alter_column("events", "event_type", type_=sa.String(50), existing_type=sa.String(30))


def downgrade() -> None:
    op.alter_column("events", "event_type", type_=sa.String(30), existing_type=sa.String(50))
    op.drop_column("hypotheses", "falsification_criteria")
