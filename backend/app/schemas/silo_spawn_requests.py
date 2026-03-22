"""Schemas for silo spawn request APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import field_validator, model_validator
from sqlmodel import SQLModel

SiloSpawnRequestStatus = Literal[
    "requested",
    "planned",
    "spawning",
    "running",
    "materialized",
    "failed",
    "cancelled",
]
SiloSpawnRequestScope = Literal["organization", "board", "silo"]
SiloSpawnRequestPriority = Literal["low", "normal", "high", "urgent"]


class SiloSpawnRequestBase(SQLModel):
    display_name: str
    silo_kind: str = "agent"
    scope: SiloSpawnRequestScope = "organization"
    priority: SiloSpawnRequestPriority = "normal"
    board_id: UUID | None = None
    parent_silo_id: UUID | None = None
    source_task_id: UUID | None = None
    desired_role: str | None = None
    source_task_title: str | None = None
    runtime_preference: str | None = None
    summary: str | None = None
    desired_state: dict[str, object] | None = None

    @field_validator(
        "display_name",
        "silo_kind",
        "desired_role",
        "runtime_preference",
        "summary",
        mode="before",
    )
    @classmethod
    def _normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return value

    @model_validator(mode="after")
    def _validate_scope(self) -> "SiloSpawnRequestBase":
        if self.display_name is None:
            raise ValueError("display_name is required")
        if self.scope == "organization":
            return self
        if self.scope == "board" and self.board_id is None:
            raise ValueError("board_id is required for board-scoped silo requests")
        if self.scope == "silo" and self.parent_silo_id is None:
            raise ValueError("parent_silo_id is required for silo-scoped silo requests")
        if self.source_task_id is not None and self.scope != "board":
            raise ValueError("source_task_id requires a board-scoped silo request")
        return self


class SiloSpawnRequestCreate(SiloSpawnRequestBase):
    pass


class SiloSpawnRequestUpdate(SQLModel):
    status: SiloSpawnRequestStatus | None = None
    priority: SiloSpawnRequestPriority | None = None
    source_task_title: str | None = None
    summary: str | None = None
    desired_state: dict[str, object] | None = None

    @field_validator("source_task_title", "summary", mode="before")
    @classmethod
    def _normalize_summary(cls, value: object) -> object:
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return value


class SiloSpawnRequestRead(SiloSpawnRequestBase):
    id: UUID
    organization_id: UUID
    requested_by_user_id: UUID | None = None
    source_task_id: UUID | None = None
    source_task_title: str | None = None
    materialized_silo_id: UUID | None = None
    materialized_silo_slug: str | None = None
    materialized_at: datetime | None = None
    slug: str
    status: SiloSpawnRequestStatus
    created_at: datetime
    updated_at: datetime
