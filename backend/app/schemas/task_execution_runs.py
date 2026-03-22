"""Schemas for task-backed execution runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import field_validator
from sqlmodel import Field, SQLModel

ExecutionRunStatus = Literal[
    "queued",
    "dispatching",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "blocked",
]


class TaskExecutionRunCreate(SQLModel):
    """Payload for creating a task-backed execution run."""

    silo_slug: str
    role_slug: str | None = None
    prompt_override: str | None = None
    branch_name_hint: str | None = None
    input_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("silo_slug", "role_slug", "prompt_override", "branch_name_hint", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        """Trim text values and collapse blank optional strings to None."""
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return value


class TaskExecutionRunUpdate(SQLModel):
    """Patch payload for updating execution run status and results."""

    status: ExecutionRunStatus | None = None
    external_run_id: str | None = None
    workspace_path: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    summary: str | None = None
    error_message: str | None = None
    issue_identifier: str | None = None
    completion_kind: str | None = None
    duration_ms: int | None = None
    result_payload: dict[str, Any] | None = None

    @field_validator(
        "external_run_id",
        "workspace_path",
        "branch_name",
        "pr_url",
        "summary",
        "error_message",
        "issue_identifier",
        "completion_kind",
        mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: object) -> object:
        """Trim text fields and collapse blank strings to None."""
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return value


class TaskExecutionRunRead(SQLModel):
    """Serialized execution run payload returned from task execution endpoints."""

    id: UUID
    organization_id: UUID
    board_id: UUID
    task_id: UUID
    silo_id: UUID
    silo_slug: str
    requested_by_user_id: UUID | None = None
    requested_by_agent_id: UUID | None = None
    executor_kind: Literal["symphony"] = "symphony"
    role_slug: str
    status: ExecutionRunStatus
    task_snapshot: dict[str, Any] | None = None
    dispatch_payload: dict[str, Any] | None = None
    result_payload: dict[str, Any] | None = None
    external_run_id: str | None = None
    workspace_path: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    summary: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TaskExecutionRunCallback(SQLModel):
    """Payload accepted from Symphony bridge callbacks."""

    status: ExecutionRunStatus
    external_run_id: str | None = None
    workspace_path: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    summary: str | None = None
    error_message: str | None = None
    issue_identifier: str | None = None
    completion_kind: str | None = None
    duration_ms: int | None = None
    result_payload: dict[str, Any] | None = None

    @field_validator(
        "external_run_id",
        "workspace_path",
        "branch_name",
        "pr_url",
        "summary",
        "error_message",
        "issue_identifier",
        "completion_kind",
        mode="before",
    )
    @classmethod
    def normalize_callback_text_fields(cls, value: object) -> object:
        """Trim callback text fields and collapse blank strings to None."""
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return value

    @field_validator("duration_ms")
    @classmethod
    def validate_duration_ms(cls, value: int | None) -> int | None:
        """Reject negative callback durations."""
        if value is not None and value < 0:
            raise ValueError("duration_ms must be >= 0")
        return value
