"""Add confidence_after column to evidence table.

Stores the hypothesis confidence value at the time each piece of evidence
was recorded, creating a natural confidence time series via the evidence list.

Revision ID: 014_confidence_after
Revises: 013_composite_indexes
Create Date: 2026-02-25
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014_confidence_after"
down_revision: Union[str, None] = "013_composite_indexes"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("evidence", sa.Column("confidence_after", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("evidence", "confidence_after")
