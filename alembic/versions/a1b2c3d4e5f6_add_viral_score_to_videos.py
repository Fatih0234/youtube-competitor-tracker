"""add viral_score to videos

Revision ID: a1b2c3d4e5f6
Revises: fd84ea383582
Create Date: 2026-03-20 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'fd84ea383582'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('videos', sa.Column('viral_score', sa.Float(), nullable=True))
    op.add_column('videos', sa.Column('viral_score_updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('videos', 'viral_score_updated_at')
    op.drop_column('videos', 'viral_score')
