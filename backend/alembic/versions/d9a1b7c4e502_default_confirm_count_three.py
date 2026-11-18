"""default alarm confirmation count to three

Revision ID: d9a1b7c4e502
Revises: c3f7a2d9e611
Create Date: 2026-11-17 18:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd9a1b7c4e502'
down_revision: str | None = 'c3f7a2d9e611'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('motors', schema=None) as batch_op:
        batch_op.alter_column(
            'temp_confirm_count',
            existing_type=sa.Integer(),
            server_default='3',
            existing_nullable=False,
        )
        batch_op.alter_column(
            'current_confirm_count',
            existing_type=sa.Integer(),
            server_default='3',
            existing_nullable=False,
        )
    op.execute("UPDATE motors SET temp_confirm_count = 3 WHERE temp_confirm_count = 2")
    op.execute("UPDATE motors SET current_confirm_count = 3 WHERE current_confirm_count = 2")


def downgrade() -> None:
    with op.batch_alter_table('motors', schema=None) as batch_op:
        batch_op.alter_column(
            'temp_confirm_count',
            existing_type=sa.Integer(),
            server_default='2',
            existing_nullable=False,
        )
        batch_op.alter_column(
            'current_confirm_count',
            existing_type=sa.Integer(),
            server_default='2',
            existing_nullable=False,
        )
