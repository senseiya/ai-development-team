"""Add run_checkpoints table for LangGraph state persistence.

Revision ID: 9e4b5c6d7f8a
Revises: 8f3a2b1c4d5e
Create Date: 2026-07-23 21:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9e4b5c6d7f8a'
down_revision: str | None = '8f3a2b1c4d5e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'run_checkpoints',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('thread_id', sa.String(length=100), nullable=False),
        sa.Column('step', sa.Integer(), nullable=False),
        sa.Column('checkpoint_data', sa.Text(), nullable=False),
        sa.Column('meta_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_run_checkpoints_run_id',
        'run_checkpoints',
        ['run_id'],
    )
    op.create_index(
        'ix_run_checkpoints_step',
        'run_checkpoints',
        ['run_id', 'step'],
    )


def downgrade() -> None:
    op.drop_index('ix_run_checkpoints_step', table_name='run_checkpoints')
    op.drop_index('ix_run_checkpoints_run_id', table_name='run_checkpoints')
    op.drop_table('run_checkpoints')
