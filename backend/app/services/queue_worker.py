"""Generic queue worker with task-type dispatch."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.contracts.telemetry import finalize_queue_worker_event_payload
from app.core.config import settings
from app.core.logging import get_logger
from app.services.openclaw.lifecycle_queue import TASK_TYPE as LIFECYCLE_RECONCILE_TASK_TYPE
from app.services.openclaw.lifecycle_queue import (
    requeue_lifecycle_queue_task,
)
from app.services.openclaw.lifecycle_reconcile import process_lifecycle_queue_task
from app.services.queue import QueuedTask, dequeue_task
from app.services.task_execution_queue import TASK_TYPE as TASK_EXECUTION_DISPATCH_TASK_TYPE
from app.services.task_execution_queue import requeue_task_execution_dispatch
from app.services.task_execution_worker import process_task_execution_dispatch_task
from app.services.webhooks.dispatch import (
    process_webhook_queue_task,
    requeue_webhook_queue_task,
)
from app.services.webhooks.queue import TASK_TYPE as WEBHOOK_TASK_TYPE

logger = get_logger(__name__)
_WORKER_BLOCK_TIMEOUT_SECONDS = 5.0


def _worker_telemetry(
    *,
    status: str,
    task_type: str | None = None,
    attempt: int | None = None,
    error: object | None = None,
    count: int | None = None,
    throttle_seconds: float | None = None,
    retry_delay_seconds: float | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "queue_name": settings.rq_queue_name,
        "status": status,
    }
    if task_type is not None:
        payload["task_type"] = task_type
    if attempt is not None:
        payload["attempt"] = attempt
    if error is not None:
        payload["error"] = str(error)
    if count is not None:
        payload["count"] = count
    if throttle_seconds is not None:
        payload["throttle_seconds"] = throttle_seconds
    if retry_delay_seconds is not None:
        payload["retry_delay_seconds"] = retry_delay_seconds
    return finalize_queue_worker_event_payload(payload)


@dataclass(frozen=True)
class _TaskHandler:
    handler: Callable[[QueuedTask], Awaitable[None]]
    attempts_to_delay: Callable[[int], float]
    requeue: Callable[[QueuedTask, float], bool]


_TASK_HANDLERS: dict[str, _TaskHandler] = {
    LIFECYCLE_RECONCILE_TASK_TYPE: _TaskHandler(
        handler=process_lifecycle_queue_task,
        attempts_to_delay=lambda attempts: min(
            settings.rq_dispatch_retry_base_seconds * (2 ** max(0, attempts)),
            settings.rq_dispatch_retry_max_seconds,
        ),
        requeue=lambda task, delay: requeue_lifecycle_queue_task(task, delay_seconds=delay),
    ),
    WEBHOOK_TASK_TYPE: _TaskHandler(
        handler=process_webhook_queue_task,
        attempts_to_delay=lambda attempts: min(
            settings.rq_dispatch_retry_base_seconds * (2 ** max(0, attempts)),
            settings.rq_dispatch_retry_max_seconds,
        ),
        requeue=lambda task, delay: requeue_webhook_queue_task(task, delay_seconds=delay),
    ),
    TASK_EXECUTION_DISPATCH_TASK_TYPE: _TaskHandler(
        handler=process_task_execution_dispatch_task,
        attempts_to_delay=lambda attempts: min(
            settings.rq_dispatch_retry_base_seconds * (2 ** max(0, attempts)),
            settings.rq_dispatch_retry_max_seconds,
        ),
        requeue=lambda task, delay: requeue_task_execution_dispatch(task, delay_seconds=delay),
    ),
}


def _compute_jitter(base_delay: float) -> float:
    return random.uniform(0, min(settings.rq_dispatch_retry_max_seconds / 10, base_delay * 0.1))


async def flush_queue(*, block: bool = False, block_timeout: float = 0) -> int:
    """Consume one queue batch and dispatch by task type."""
    processed = 0
    while True:
        try:
            task = dequeue_task(
                settings.rq_queue_name,
                redis_url=settings.rq_redis_url,
                block=block,
                block_timeout=block_timeout,
            )
        except Exception:
            logger.exception(
                "queue.worker.dequeue_failed",
                extra=_worker_telemetry(status="dequeue_failed"),
            )
            continue

        if task is None:
            break

        handler = _TASK_HANDLERS.get(task.task_type)
        if handler is None:
            logger.warning(
                "queue.worker.task_unhandled",
                extra=_worker_telemetry(status="task_unhandled", task_type=task.task_type),
            )
            continue

        try:
            await handler.handler(task)
            processed += 1
            logger.info(
                "queue.worker.success",
                extra=_worker_telemetry(
                    status="succeeded",
                    task_type=task.task_type,
                    attempt=task.attempts,
                ),
            )
        except Exception as exc:
            logger.exception(
                "queue.worker.failed",
                extra=_worker_telemetry(
                    status="failed",
                    task_type=task.task_type,
                    attempt=task.attempts,
                    error=exc,
                ),
            )
            base_delay = handler.attempts_to_delay(task.attempts)
            delay = base_delay + _compute_jitter(base_delay)
            if not handler.requeue(task, delay):
                logger.warning(
                    "queue.worker.drop_task",
                    extra=_worker_telemetry(
                        status="dropped",
                        task_type=task.task_type,
                        attempt=task.attempts,
                        retry_delay_seconds=delay,
                    ),
                )
        await asyncio.sleep(settings.rq_dispatch_throttle_seconds)

    if processed > 0:
        logger.info(
            "queue.worker.batch_complete",
            extra=_worker_telemetry(status="batch_complete", count=processed),
        )
    return processed


async def _run_worker_loop() -> None:
    while True:
        try:
            await flush_queue(
                block=True,
                # Keep a finite timeout so scheduled tasks are periodically drained.
                block_timeout=_WORKER_BLOCK_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception(
                "queue.worker.loop_failed",
                extra=_worker_telemetry(status="loop_failed"),
            )
            await asyncio.sleep(1)


def run_worker() -> None:
    """RQ entrypoint for running continuous queue processing."""
    logger.info(
        "queue.worker.batch_started",
        extra=_worker_telemetry(
            status="batch_started",
            throttle_seconds=settings.rq_dispatch_throttle_seconds,
        ),
    )
    try:
        asyncio.run(_run_worker_loop())
    finally:
        logger.info("queue.worker.stopped", extra=_worker_telemetry(status="stopped"))
