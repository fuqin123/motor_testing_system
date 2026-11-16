"""add operating state profiles and reading state

Revision ID: a5c1e9f2b304
Revises: 790d0fedfa18
Create Date: 2026-11-13 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a5c1e9f2b304'
down_revision: str | None = '790d0fedfa18'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('motors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vibration_deviation_pct', sa.Float(), nullable=False, server_default='30'))
        batch_op.add_column(sa.Column('off_current_max_a', sa.Float(), nullable=False, server_default='0.5'))
        batch_op.add_column(sa.Column('running_current_min_a', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('state_running_current_a', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('state_running_temp_c', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('state_running_vibration_mm_s', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('state_standby_current_a', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('state_standby_temp_c', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('state_standby_vibration_mm_s', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('state_off_current_a', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('state_off_temp_c', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('state_off_vibration_mm_s', sa.Float(), nullable=False, server_default='0'))

    with op.batch_alter_table('readings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('operating_state', sa.String(length=16), nullable=False, server_default='unknown'))


def downgrade() -> None:
    with op.batch_alter_table('readings', schema=None) as batch_op:
        batch_op.drop_column('operating_state')

    with op.batch_alter_table('motors', schema=None) as batch_op:
        batch_op.drop_column('state_off_vibration_mm_s')
        batch_op.drop_column('state_off_temp_c')
        batch_op.drop_column('state_off_current_a')
        batch_op.drop_column('state_standby_vibration_mm_s')
        batch_op.drop_column('state_standby_temp_c')
        batch_op.drop_column('state_standby_current_a')
        batch_op.drop_column('state_running_vibration_mm_s')
        batch_op.drop_column('state_running_temp_c')
        batch_op.drop_column('state_running_current_a')
        batch_op.drop_column('running_current_min_a')
        batch_op.drop_column('off_current_max_a')
        batch_op.drop_column('vibration_deviation_pct')
