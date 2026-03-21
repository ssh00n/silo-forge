"""Persisted silo control-plane records."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class Silo(QueryModel, table=True):
    """Top-level silo record tracked by the control plane."""

    __tablename__ = "silos"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_silos_org_slug"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    slug: str = Field(index=True)
    name: str
    blueprint_slug: str = Field(index=True)
    blueprint_version: str
    owner_display_name: str | None = None
    status: str = Field(default="draft", index=True)
    enable_symphony: bool = Field(default=False)
    enable_telemetry: bool = Field(default=False)
    desired_state: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
