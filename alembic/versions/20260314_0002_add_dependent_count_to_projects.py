"""add dependent_count to projects

Revision ID: 20260314_0002
Revises: 20260306_0001
Create Date: 2026-03-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260314_0002"
down_revision = "20260306_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("dependent_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "dependent_count")
