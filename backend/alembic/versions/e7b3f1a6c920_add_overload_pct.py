"""add overload percentage

Revision ID: e7b3f1a6c920
Revises: d9a1b7c4e502
Create Date: 2026-11-18 20:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'e7b3f1a6c920'
down_revision: str | None = 'd9a1b7c4e502'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('motors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('overload_pct', sa.Float(), nullable=False, server_default='10'))


def downgrade() -> None:
    with op.batch_alter_table('motors', schema=None) as batch_op:
        batch_op.drop_column('overload_pct')
