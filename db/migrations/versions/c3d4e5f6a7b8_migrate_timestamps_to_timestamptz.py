"""Migrate timestamp columns to TIMESTAMPTZ for timezone-aware datetimes.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-24 04:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All (table, column) pairs that need TIMESTAMP -> TIMESTAMPTZ
TIMESTAMP_COLUMNS: list[tuple[str, str]] = [
    ("runs", "created_at"),
    ("runs", "updated_at"),
    ("model_profiles", "created_at"),
    ("model_profiles", "updated_at"),
    ("run_checkpoints", "created_at"),
    ("users", "created_at"),
    ("users", "updated_at"),
    ("api_keys", "created_at"),
    ("file_changes", "created_at"),
]


def upgrade() -> None:
    for table, column in TIMESTAMP_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
        )


def downgrade() -> None:
    for table, column in TIMESTAMP_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
