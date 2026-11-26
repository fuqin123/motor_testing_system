"""add packet loss attempt history

Revision ID: b7d4e2a91c33
Revises: f2c6e8a4d701
Create Date: 2026-11-26 11:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d4e2a91c33'
down_revision: str | None = 'f2c6e8a4d701'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'packet_loss_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('packet_loss_id', sa.Integer(), nullable=False),
        sa.Column('attempt_no', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['packet_loss_id'], ['packet_losses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('packet_loss_attempts', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_packet_loss_attempts_packet_loss_id'), ['packet_loss_id'], unique=False
        )
        batch_op.create_index(
            'ix_packet_loss_attempts_loss_time',
            ['packet_loss_id', 'attempted_at'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('packet_loss_attempts', schema=None) as batch_op:
        batch_op.drop_index('ix_packet_loss_attempts_loss_time')
        batch_op.drop_index(batch_op.f('ix_packet_loss_attempts_packet_loss_id'))
    op.drop_table('packet_loss_attempts')
