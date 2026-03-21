"""add task execution runs

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a
Create Date: 2026-03-20 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_execution_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("board_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("silo_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by_agent_id", sa.Uuid(), nullable=True),
        sa.Column("executor_kind", sa.String(), nullable=False),
        sa.Column("role_slug", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("task_snapshot", sa.JSON(), nullable=True),
        sa.Column("dispatch_payload", sa.JSON(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("external_run_id", sa.String(), nullable=True),
        sa.Column("workspace_path", sa.String(), nullable=True),
        sa.Column("branch_name", sa.String(), nullable=True),
        sa.Column("pr_url", sa.String(), nullable=True),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["requested_by_agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["silo_id"], ["silos.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_task_execution_runs_board_id"),
        "task_execution_runs",
        ["board_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_execution_runs_executor_kind"),
        "task_execution_runs",
        ["executor_kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_execution_runs_external_run_id"),
        "task_execution_runs",
        ["external_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_execution_runs_organization_id"),
        "task_execution_runs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_execution_runs_requested_by_agent_id"),
        "task_execution_runs",
        ["requested_by_agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_execution_runs_requested_by_user_id"),
        "task_execution_runs",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_execution_runs_role_slug"),
        "task_execution_runs",
        ["role_slug"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_execution_runs_silo_id"),
        "task_execution_runs",
        ["silo_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_execution_runs_status"),
        "task_execution_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_execution_runs_task_id"),
        "task_execution_runs",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_task_execution_runs_task_id"), table_name="task_execution_runs")
    op.drop_index(op.f("ix_task_execution_runs_status"), table_name="task_execution_runs")
    op.drop_index(op.f("ix_task_execution_runs_silo_id"), table_name="task_execution_runs")
    op.drop_index(op.f("ix_task_execution_runs_role_slug"), table_name="task_execution_runs")
    op.drop_index(
        op.f("ix_task_execution_runs_requested_by_user_id"),
        table_name="task_execution_runs",
    )
    op.drop_index(
        op.f("ix_task_execution_runs_requested_by_agent_id"),
        table_name="task_execution_runs",
    )
    op.drop_index(
        op.f("ix_task_execution_runs_organization_id"),
        table_name="task_execution_runs",
    )
    op.drop_index(
        op.f("ix_task_execution_runs_external_run_id"),
        table_name="task_execution_runs",
    )
    op.drop_index(
        op.f("ix_task_execution_runs_executor_kind"),
        table_name="task_execution_runs",
    )
    op.drop_index(op.f("ix_task_execution_runs_board_id"), table_name="task_execution_runs")
    op.drop_table("task_execution_runs")
