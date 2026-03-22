"""add silo request task snapshots

Revision ID: a1b2c3d4e5f6
Revises: f7c1a2b3d4e5
Create Date: 2026-03-22 00:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f7c1a2b3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "silo_spawn_requests",
        sa.Column("source_task_status", sa.String(), nullable=True),
    )
    op.add_column(
        "silo_spawn_requests",
        sa.Column("source_task_priority", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("silo_spawn_requests", "source_task_priority")
    op.drop_column("silo_spawn_requests", "source_task_status")
