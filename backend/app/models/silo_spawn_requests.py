"""Persisted silo spawn requests for control-plane lifecycle management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped

RUNTIME_ANNOTATION_TYPES = (datetime,)


class SiloSpawnRequest(TenantScoped, table=True):
    """Desired-state record for requesting a new silo operating unit."""

    __tablename__ = "silo_spawn_requests"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_silo_spawn_requests_org_slug",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    board_id: UUID | None = Field(default=None, foreign_key="boards.id", index=True)
    parent_silo_id: UUID | None = Field(default=None, foreign_key="silos.id", index=True)
    source_task_id: UUID | None = Field(default=None, foreign_key="tasks.id", index=True)
    requested_by_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    materialized_silo_id: UUID | None = Field(default=None, foreign_key="silos.id", index=True)
    materialized_silo_slug: str | None = None

    slug: str = Field(index=True)
    display_name: str
    silo_kind: str = Field(default="agent", index=True)
    scope: str = Field(default="organization", index=True)
    priority: str = Field(default="normal", index=True)
    desired_role: str | None = None
    source_task_title: str | None = None
    source_task_status: str | None = None
    source_task_priority: str | None = None
    runtime_preference: str | None = None
    status: str = Field(default="requested", index=True)
    summary: str | None = None
    desired_state: dict[str, object] | None = Field(default=None, sa_column=Column(JSON))
    materialized_at: datetime | None = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
