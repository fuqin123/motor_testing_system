"""add packet loss retry records

Revision ID: f2c6e8a4d701
Revises: e7b3f1a6c920
Create Date: 2026-11-20 11:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'f2c6e8a4d701'
down_revision: str | None = 'e7b3f1a6c920'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'packet_losses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=160), nullable=False),
        sa.Column('cycle_ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('gateway_id', sa.Integer(), nullable=False),
        sa.Column('gateway_code', sa.String(length=32), nullable=False),
        sa.Column('sensor_id', sa.Integer(), nullable=True),
        sa.Column('sensor_code', sa.String(length=32), nullable=True),
        sa.Column('motor_id', sa.Integer(), nullable=True),
        sa.Column('motor_code', sa.String(length=32), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='pending'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recovered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['gateway_id'], ['gateways.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['motor_id'], ['motors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sensor_id'], ['sensors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_packet_loss_key'),
    )
    with op.batch_alter_table('packet_losses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_packet_losses_cycle_ts'), ['cycle_ts'], unique=False)
        batch_op.create_index(batch_op.f('ix_packet_losses_gateway_id'), ['gateway_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_packet_losses_motor_id'), ['motor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_packet_losses_sensor_id'), ['sensor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_packet_losses_status'), ['status'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('packet_losses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_packet_losses_status'))
        batch_op.drop_index(batch_op.f('ix_packet_losses_sensor_id'))
        batch_op.drop_index(batch_op.f('ix_packet_losses_motor_id'))
        batch_op.drop_index(batch_op.f('ix_packet_losses_gateway_id'))
        batch_op.drop_index(batch_op.f('ix_packet_losses_cycle_ts'))
    op.drop_table('packet_losses')
