"""Persisted task-backed execution runs for Symphony-style orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class TaskExecutionRun(QueryModel, table=True):
    """One execution attempt dispatched from a Mission Control task."""

    __tablename__ = "task_execution_runs"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    board_id: UUID = Field(foreign_key="boards.id", index=True)
    task_id: UUID = Field(foreign_key="tasks.id", index=True)
    silo_id: UUID = Field(foreign_key="silos.id", index=True)
    requested_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    requested_by_agent_id: UUID | None = Field(default=None, foreign_key="agents.id", index=True)
    executor_kind: str = Field(default="symphony", index=True)
    role_slug: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    task_snapshot: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    dispatch_payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    result_payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    external_run_id: str | None = Field(default=None, index=True)
    workspace_path: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    summary: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
