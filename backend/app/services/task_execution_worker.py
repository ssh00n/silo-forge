"""Worker handlers for background task execution dispatch."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import async_session_maker
from app.schemas.task_execution_runs import TaskExecutionRunCallback, TaskExecutionRunRead
from app.services.queue import QueuedTask
from app.services.task_execution_runs import TaskExecutionRunService
from app.services.task_execution_queue import decode_task_execution_dispatch_task

logger = get_logger(__name__)


async def _maybe_simulate_stub_callback_loop(
    *,
    dispatched_run: TaskExecutionRunRead,
    session_factory: Callable[[], object] = async_session_maker,
) -> None:
    """Close the local loop for stub dispatches when no real bridge is configured."""
    dispatch_acceptance = None
    if isinstance(dispatched_run.result_payload, dict):
        raw_acceptance = dispatched_run.result_payload.get("dispatch_acceptance")
        if isinstance(raw_acceptance, dict):
            dispatch_acceptance = raw_acceptance
    adapter_mode = (
        str(dispatch_acceptance.get("adapter_mode")).strip()
        if isinstance(dispatch_acceptance, dict) and dispatch_acceptance.get("adapter_mode")
        else None
    )
    if adapter_mode != "stub" or not settings.symphony_stub_auto_callback:
        return

    logger.info(
        "task_execution.stub_callback.start",
        extra={
            "run_id": str(dispatched_run.id),
            "external_run_id": dispatched_run.external_run_id,
            "adapter_mode": adapter_mode,
        },
    )
    running_summary = "Local stub bridge accepted the run and started execution."
    succeeded_summary = "Local stub bridge completed the run and reported success."
    if settings.symphony_stub_callback_delay_seconds > 0:
        await asyncio.sleep(settings.symphony_stub_callback_delay_seconds)
    async with session_factory() as session:
        await TaskExecutionRunService(session).update_run_by_id(
            run_id=dispatched_run.id,
            payload=TaskExecutionRunCallback(
                status="running",
                external_run_id=dispatched_run.external_run_id,
                workspace_path=dispatched_run.workspace_path,
                branch_name=dispatched_run.branch_name,
                summary=running_summary,
            ),
        )
    if settings.symphony_stub_callback_delay_seconds > 0:
        await asyncio.sleep(settings.symphony_stub_callback_delay_seconds)
    async with session_factory() as session:
        await TaskExecutionRunService(session).update_run_by_id(
            run_id=dispatched_run.id,
            payload=TaskExecutionRunCallback(
                status="succeeded",
                external_run_id=dispatched_run.external_run_id,
                workspace_path=dispatched_run.workspace_path,
                branch_name=dispatched_run.branch_name,
                summary=succeeded_summary,
                result_payload={
                    "usage": {"total_tokens": 144},
                    "adapter_mode": "stub",
                    "completion_kind": "local_stub_callback",
                },
            ),
        )
    logger.info(
        "task_execution.stub_callback.complete",
        extra={
            "run_id": str(dispatched_run.id),
            "external_run_id": dispatched_run.external_run_id,
        },
    )


async def process_task_execution_dispatch_task(task: QueuedTask) -> None:
    """Dispatch one queued task execution run through the Symphony adapter."""
    payload = decode_task_execution_dispatch_task(task)
    async with async_session_maker() as session:
        service = TaskExecutionRunService(session)
        dispatched = await service.dispatch_run(
            organization_id=payload.organization_id,
            board_id=payload.board_id,
            task_id=payload.task_id,
            run_id=payload.run_id,
        )
        await _maybe_simulate_stub_callback_loop(
            dispatched_run=dispatched,
        )
