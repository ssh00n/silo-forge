"""Queue payload helpers for task-backed execution dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.time import utcnow
from app.contracts.queue import (
    finalize_task_execution_dispatch_queue_payload,
    parse_task_execution_dispatch_queue_payload,
)
from app.services.queue import QueuedTask, enqueue_task
from app.services.queue import requeue_if_failed as generic_requeue_if_failed

TASK_TYPE = "task_execution_dispatch"


@dataclass(frozen=True)
class QueuedTaskExecutionDispatch:
    """Queued payload metadata for dispatching one task execution run."""

    organization_id: UUID
    board_id: UUID
    task_id: UUID
    run_id: UUID
    attempts: int = 0


def _task_from_payload(payload: QueuedTaskExecutionDispatch) -> QueuedTask:
    normalized_payload = finalize_task_execution_dispatch_queue_payload(
        {
            "organization_id": str(payload.organization_id),
            "board_id": str(payload.board_id),
            "task_id": str(payload.task_id),
            "run_id": str(payload.run_id),
        }
    )
    return QueuedTask(
        task_type=TASK_TYPE,
        payload=normalized_payload,
        created_at=utcnow(),
        attempts=payload.attempts,
    )


def decode_task_execution_dispatch_task(task: QueuedTask) -> QueuedTaskExecutionDispatch:
    """Decode the generic queue envelope into a typed dispatch payload."""
    if task.task_type not in {TASK_TYPE, "legacy"}:
        raise ValueError(f"Unexpected task_type={task.task_type!r}; expected {TASK_TYPE!r}")
    payload: dict[str, Any] = task.payload
    parsed = parse_task_execution_dispatch_queue_payload(payload)
    return QueuedTaskExecutionDispatch(
        organization_id=UUID(parsed.organization_id),
        board_id=UUID(parsed.board_id),
        task_id=UUID(parsed.task_id),
        run_id=UUID(parsed.run_id),
        attempts=int(payload.get("attempts", task.attempts)),
    )


def enqueue_task_execution_dispatch(payload: QueuedTaskExecutionDispatch) -> bool:
    """Enqueue a task execution run for background dispatch."""
    return enqueue_task(
        _task_from_payload(payload),
        settings.rq_queue_name,
        redis_url=settings.rq_redis_url,
    )


def requeue_task_execution_dispatch(task: QueuedTask, *, delay_seconds: float = 0) -> bool:
    """Requeue a failed execution dispatch task with capped retries."""
    return generic_requeue_if_failed(
        task,
        settings.rq_queue_name,
        max_retries=settings.rq_dispatch_max_retries,
        redis_url=settings.rq_redis_url,
        delay_seconds=max(0.0, delay_seconds),
    )
