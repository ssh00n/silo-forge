"""Persisted runtime operation history for silos."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class SiloRuntimeOperation(QueryModel, table=True):
    """One validate/apply run executed against a persisted silo."""

    __tablename__ = "silo_runtime_operations"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    silo_id: UUID = Field(foreign_key="silos.id", index=True)
    mode: str = Field(index=True)
    warnings: list[str] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SiloRuntimeOperationResult(QueryModel, table=True):
    """One per-role runtime result row for a silo validate/apply run."""

    __tablename__ = "silo_runtime_operation_results"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    operation_id: UUID = Field(foreign_key="silo_runtime_operations.id", index=True)
    role_slug: str = Field(index=True)
    runtime_kind: str = Field(index=True)
    gateway_name: str | None = None
    supports_picoclaw_bundle_apply: bool = Field(default=False)
    validated: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    applied: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    warnings: list[str] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
