"""Helpers for persisting operational telemetry as activity events."""

from __future__ import annotations

from uuid import UUID

from app.db.session import async_session_maker
from app.services.activity_log import record_activity


def _telemetry_message(*, event_type: str, payload: dict[str, object]) -> str:
    if event_type.startswith("queue.worker."):
        status = str(payload.get("status") or "updated")
        task_type = payload.get("task_type")
        if task_type:
            return f"Queue worker {status} {task_type}."
        return f"Queue worker {status}."
    if event_type.startswith("webhook.dispatch."):
        status = str(payload.get("status") or "updated")
        payload_id = payload.get("payload_id")
        if payload_id:
            return f"Webhook dispatch {status} for payload {payload_id}."
        return f"Webhook dispatch {status}."
    return event_type


async def record_telemetry_activity(
    *,
    event_type: str,
    payload: dict[str, object],
    board_id: UUID | None = None,
) -> None:
    async with async_session_maker() as session:
        record_activity(
            session,
            event_type=event_type,
            message=_telemetry_message(event_type=event_type, payload=payload),
            payload=payload,
            board_id=board_id,
        )
        await session.commit()
