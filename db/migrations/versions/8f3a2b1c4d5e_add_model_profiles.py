"""Add model_profiles table for automatic model routing.

Revision ID: 8f3a2b1c4d5e
Revises: 1ae4fbe91d93
Create Date: 2026-07-23 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f3a2b1c4d5e"
down_revision: str | None = "1ae4fbe91d93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("capabilities", sa.Text(), nullable=False),
        sa.Column("cost_per_1k_input", sa.Float(), nullable=False),
        sa.Column("cost_per_1k_output", sa.Float(), nullable=False),
        sa.Column("max_context", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_model_profiles_provider",
        "model_profiles",
        ["provider"],
    )
    op.create_index(
        "ix_model_profiles_enabled",
        "model_profiles",
        ["enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_model_profiles_enabled", table_name="model_profiles")
    op.drop_index("ix_model_profiles_provider", table_name="model_profiles")
    op.drop_table("model_profiles")
