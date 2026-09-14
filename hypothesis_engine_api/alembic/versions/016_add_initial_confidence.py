"""Add initial_confidence column to hypotheses.

Immutable field set at creation time, used by metrics service for accurate
Brier score, calibration, and prediction value computation. Backfilled
from current confidence for existing rows.

Revision ID: 016_initial_confidence
Revises: 015_add_channels
Create Date: 2026-02-27
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "016_initial_confidence"
down_revision: Union[str, None] = "015_add_channels"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("hypotheses", sa.Column("initial_confidence", sa.Float(), nullable=True))
    # Backfill: set initial_confidence = confidence for existing rows
    op.execute("UPDATE hypotheses SET initial_confidence = confidence WHERE initial_confidence IS NULL")


def downgrade() -> None:
    op.drop_column("hypotheses", "initial_confidence")
