"""Persisted per-role silo assignment records."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class SiloRole(QueryModel, table=True):
    """One resolved role assignment within a persisted silo."""

    __tablename__ = "silo_roles"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (UniqueConstraint("silo_id", "slug", name="uq_silo_roles_silo_slug"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    silo_id: UUID = Field(foreign_key="silos.id", index=True)
    slug: str = Field(index=True)
    display_name: str
    role_type: str = Field(index=True)
    runtime_kind: str = Field(index=True)
    host_kind: str
    default_model: str | None = None
    fallback_model: str | None = None
    channel_name: str | None = None
    gateway_id: UUID | None = Field(default=None, foreign_key="gateways.id", index=True)
    gateway_name: str | None = None
    workspace_root: str | None = None
    secret_bindings: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
