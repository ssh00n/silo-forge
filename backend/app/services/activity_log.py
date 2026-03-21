"""Utilities for recording normalized activity events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.activity_events import ActivityEvent


def record_activity(
    session: AsyncSession,
    *,
    event_type: str,
    message: str,
    payload: dict[str, Any] | None = None,
    agent_id: UUID | None = None,
    task_id: UUID | None = None,
    board_id: UUID | None = None,
) -> ActivityEvent:
    """Create and attach an activity event row to the current DB session."""
    event = ActivityEvent(
        event_type=event_type,
        message=message,
        payload=payload,
        agent_id=agent_id,
        task_id=task_id,
        board_id=board_id,
    )
    session.add(event)
    return event
