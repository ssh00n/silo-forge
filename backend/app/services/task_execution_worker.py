"""Worker handlers for background task execution dispatch."""

from __future__ import annotations

from app.db.session import async_session_maker
from app.services.queue import QueuedTask
from app.services.task_execution_runs import TaskExecutionRunService
from app.services.task_execution_queue import decode_task_execution_dispatch_task


async def process_task_execution_dispatch_task(task: QueuedTask) -> None:
    """Dispatch one queued task execution run through the Symphony adapter."""
    payload = decode_task_execution_dispatch_task(task)
    async with async_session_maker() as session:
        await TaskExecutionRunService(session).dispatch_run(
            organization_id=payload.organization_id,
            board_id=payload.board_id,
            task_id=payload.task_id,
            run_id=payload.run_id,
        )
