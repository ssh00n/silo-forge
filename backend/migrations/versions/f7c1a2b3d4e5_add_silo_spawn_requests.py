"""add silo spawn requests

Revision ID: f7c1a2b3d4e5
Revises: d4e5f6a7b8c9
Create Date: 2026-03-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7c1a2b3d4e5"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "silo_spawn_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("board_id", sa.Uuid(), nullable=True),
        sa.Column("parent_silo_id", sa.Uuid(), nullable=True),
        sa.Column("source_task_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("materialized_silo_id", sa.Uuid(), nullable=True),
        sa.Column("materialized_silo_slug", sa.String(), nullable=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("silo_kind", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("desired_role", sa.String(), nullable=True),
        sa.Column("source_task_title", sa.String(), nullable=True),
        sa.Column("runtime_preference", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("desired_state", sa.JSON(), nullable=True),
        sa.Column("materialized_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["materialized_silo_id"], ["silos.id"]),
        sa.ForeignKeyConstraint(["parent_silo_id"], ["silos.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_silo_spawn_requests_org_slug",
        ),
    )
    op.create_index(
        op.f("ix_silo_spawn_requests_board_id"),
        "silo_spawn_requests",
        ["board_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_spawn_requests_materialized_silo_id"),
        "silo_spawn_requests",
        ["materialized_silo_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_spawn_requests_source_task_id"),
        "silo_spawn_requests",
        ["source_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_spawn_requests_priority"),
        "silo_spawn_requests",
        ["priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_spawn_requests_organization_id"),
        "silo_spawn_requests",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_spawn_requests_parent_silo_id"),
        "silo_spawn_requests",
        ["parent_silo_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_spawn_requests_requested_by_user_id"),
        "silo_spawn_requests",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_spawn_requests_scope"),
        "silo_spawn_requests",
        ["scope"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_spawn_requests_silo_kind"),
        "silo_spawn_requests",
        ["silo_kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_spawn_requests_slug"),
        "silo_spawn_requests",
        ["slug"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_spawn_requests_status"),
        "silo_spawn_requests",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_silo_spawn_requests_priority"), table_name="silo_spawn_requests")
    op.drop_index(op.f("ix_silo_spawn_requests_source_task_id"), table_name="silo_spawn_requests")
    op.drop_index(
        op.f("ix_silo_spawn_requests_materialized_silo_id"),
        table_name="silo_spawn_requests",
    )
    op.drop_index(op.f("ix_silo_spawn_requests_status"), table_name="silo_spawn_requests")
    op.drop_index(op.f("ix_silo_spawn_requests_slug"), table_name="silo_spawn_requests")
    op.drop_index(op.f("ix_silo_spawn_requests_silo_kind"), table_name="silo_spawn_requests")
    op.drop_index(op.f("ix_silo_spawn_requests_scope"), table_name="silo_spawn_requests")
    op.drop_index(
        op.f("ix_silo_spawn_requests_requested_by_user_id"),
        table_name="silo_spawn_requests",
    )
    op.drop_index(
        op.f("ix_silo_spawn_requests_parent_silo_id"),
        table_name="silo_spawn_requests",
    )
    op.drop_index(
        op.f("ix_silo_spawn_requests_organization_id"),
        table_name="silo_spawn_requests",
    )
    op.drop_index(op.f("ix_silo_spawn_requests_board_id"), table_name="silo_spawn_requests")
    op.drop_table("silo_spawn_requests")
