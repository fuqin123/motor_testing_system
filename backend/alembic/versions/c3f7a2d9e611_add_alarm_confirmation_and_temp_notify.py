"""add alarm confirmation counts and temperature notify base

Revision ID: c3f7a2d9e611
Revises: a5c1e9f2b304
Create Date: 2026-11-16 14:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c3f7a2d9e611'
down_revision: str | None = 'a5c1e9f2b304'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('motors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('temp_notify_base_c', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('temp_confirm_count', sa.Integer(), nullable=False, server_default='2'))
        batch_op.add_column(sa.Column('current_confirm_count', sa.Integer(), nullable=False, server_default='2'))

    op.create_table(
        'alarm_streaks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('motor_id', sa.Integer(), nullable=False),
        sa.Column('rule_key', sa.String(length=32), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('last_ts', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['motor_id'], ['motors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('motor_id', 'rule_key', name='uq_alarm_streak_motor_rule'),
    )
    with op.batch_alter_table('alarm_streaks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alarm_streaks_motor_id'), ['motor_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('alarm_streaks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alarm_streaks_motor_id'))
    op.drop_table('alarm_streaks')

    with op.batch_alter_table('motors', schema=None) as batch_op:
        batch_op.drop_column('current_confirm_count')
        batch_op.drop_column('temp_confirm_count')
        batch_op.drop_column('temp_notify_base_c')
