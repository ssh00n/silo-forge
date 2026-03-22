"""Task-backed execution run APIs for Symphony integration scaffolding."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.db.session import get_session
from app.models.boards import Board
from app.models.tasks import Task
from app.schemas.task_execution_runs import (
    TaskExecutionRunCreate,
    TaskExecutionRunRead,
    TaskExecutionRunUpdate,
)
from app.services.organizations import OrganizationContext
from app.services.task_execution_queue import (
    QueuedTaskExecutionDispatch,
    enqueue_task_execution_dispatch,
)
from app.services.task_execution_runs import TaskExecutionRunService

router = APIRouter(
    prefix="/boards/{board_id}/tasks/{task_id}/execution-runs",
    tags=["task-execution"],
)
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)


async def _enqueue_or_dispatch_immediately(
    *,
    service: TaskExecutionRunService,
    organization_id: UUID,
    board_id: UUID,
    task_id: UUID,
    run_id: UUID,
) -> TaskExecutionRunRead:
    queued = enqueue_task_execution_dispatch(
        QueuedTaskExecutionDispatch(
            organization_id=organization_id,
            board_id=board_id,
            task_id=task_id,
            run_id=run_id,
        ),
    )
    if queued:
        run = await service.get_run(
            organization_id=organization_id,
            board_id=board_id,
            task_id=task_id,
            run_id=run_id,
        )
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution run not found",
            )
        return run
    return await service.dispatch_run(
        organization_id=organization_id,
        board_id=board_id,
        task_id=task_id,
        run_id=run_id,
    )


async def _get_board_and_task(
    *,
    session: AsyncSession,
    ctx: OrganizationContext,
    board_id: UUID,
    task_id: UUID,
) -> tuple[Board, Task]:
    board = await session.get(Board, board_id)
    if board is None or board.organization_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    task = await session.get(Task, task_id)
    if task is None or task.board_id != board.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return board, task


@router.get("", response_model=list[TaskExecutionRunRead])
async def list_task_execution_runs(
    board_id: UUID,
    task_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> list[TaskExecutionRunRead]:
    """List execution runs for one task."""
    board, task = await _get_board_and_task(
        session=session,
        ctx=ctx,
        board_id=board_id,
        task_id=task_id,
    )
    return await TaskExecutionRunService(session).list_runs(
        organization_id=ctx.organization.id,
        board_id=board.id,
        task_id=task.id,
    )


@router.post("", response_model=TaskExecutionRunRead, status_code=status.HTTP_201_CREATED)
async def create_task_execution_run(
    board_id: UUID,
    task_id: UUID,
    payload: TaskExecutionRunCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> TaskExecutionRunRead:
    """Create a new queued execution run for one task."""
    board, task = await _get_board_and_task(
        session=session,
        ctx=ctx,
        board_id=board_id,
        task_id=task_id,
    )
    service = TaskExecutionRunService(session)
    try:
        return await service.create_run(
            board=board,
            task=task,
            payload=payload,
            requested_by_user_id=ctx.member.user_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        if detail.endswith("not found"):
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/dispatch", response_model=TaskExecutionRunRead, status_code=status.HTTP_201_CREATED)
async def create_and_dispatch_task_execution_run(
    board_id: UUID,
    task_id: UUID,
    payload: TaskExecutionRunCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> TaskExecutionRunRead:
    """Create a new execution run and immediately queue it for Symphony dispatch."""
    board, task = await _get_board_and_task(
        session=session,
        ctx=ctx,
        board_id=board_id,
        task_id=task_id,
    )
    service = TaskExecutionRunService(session)
    try:
        run = await service.create_run(
            board=board,
            task=task,
            payload=payload,
            requested_by_user_id=ctx.member.user_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        if detail.endswith("not found"):
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return await _enqueue_or_dispatch_immediately(
        service=service,
        organization_id=ctx.organization.id,
        board_id=board.id,
        task_id=task.id,
        run_id=run.id,
    )


@router.get("/{run_id}", response_model=TaskExecutionRunRead)
async def get_task_execution_run(
    board_id: UUID,
    task_id: UUID,
    run_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> TaskExecutionRunRead:
    """Return one execution run for one task."""
    board, task = await _get_board_and_task(
        session=session,
        ctx=ctx,
        board_id=board_id,
        task_id=task_id,
    )
    run = await TaskExecutionRunService(session).get_run(
        organization_id=ctx.organization.id,
        board_id=board.id,
        task_id=task.id,
        run_id=run_id,
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution run not found")
    return run


@router.patch("/{run_id}", response_model=TaskExecutionRunRead)
async def update_task_execution_run(
    board_id: UUID,
    task_id: UUID,
    run_id: UUID,
    payload: TaskExecutionRunUpdate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> TaskExecutionRunRead:
    """Update one execution run for one task."""
    board, task = await _get_board_and_task(
        session=session,
        ctx=ctx,
        board_id=board_id,
        task_id=task_id,
    )
    try:
        return await TaskExecutionRunService(session).update_run(
            organization_id=ctx.organization.id,
            board=board,
            task=task,
            run_id=run_id,
            payload=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if detail.endswith("not found")
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/{run_id}/dispatch", response_model=TaskExecutionRunRead)
async def dispatch_task_execution_run(
    board_id: UUID,
    task_id: UUID,
    run_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> TaskExecutionRunRead:
    """Queue one execution run for background Symphony dispatch."""
    board, task = await _get_board_and_task(
        session=session,
        ctx=ctx,
        board_id=board_id,
        task_id=task_id,
    )
    service = TaskExecutionRunService(session)
    run = await service.get_run(
        organization_id=ctx.organization.id,
        board_id=board.id,
        task_id=task.id,
        run_id=run_id,
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution run not found")
    return await _enqueue_or_dispatch_immediately(
        service=service,
        organization_id=ctx.organization.id,
        board_id=board.id,
        task_id=task.id,
        run_id=run_id,
    )


@router.post(
    "/{run_id}/retry", response_model=TaskExecutionRunRead, status_code=status.HTTP_201_CREATED
)
async def retry_task_execution_run(
    board_id: UUID,
    task_id: UUID,
    run_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> TaskExecutionRunRead:
    """Retry a terminal execution run by cloning it into a new queued run."""
    board, task = await _get_board_and_task(
        session=session,
        ctx=ctx,
        board_id=board_id,
        task_id=task_id,
    )
    try:
        return await TaskExecutionRunService(session).retry_run(
            organization_id=ctx.organization.id,
            board=board,
            task=task,
            run_id=run_id,
            requested_by_user_id=ctx.member.user_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if detail.endswith("not found")
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post(
    "/{run_id}/retry-dispatch",
    response_model=TaskExecutionRunRead,
    status_code=status.HTTP_201_CREATED,
)
async def retry_and_dispatch_task_execution_run(
    board_id: UUID,
    task_id: UUID,
    run_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> TaskExecutionRunRead:
    """Retry a terminal run and immediately queue the replacement for dispatch."""
    board, task = await _get_board_and_task(
        session=session,
        ctx=ctx,
        board_id=board_id,
        task_id=task_id,
    )
    try:
        retried = await TaskExecutionRunService(session).retry_run(
            organization_id=ctx.organization.id,
            board=board,
            task=task,
            run_id=run_id,
            requested_by_user_id=ctx.member.user_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if detail.endswith("not found")
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return await _enqueue_or_dispatch_immediately(
        service=TaskExecutionRunService(session),
        organization_id=ctx.organization.id,
        board_id=board.id,
        task_id=task.id,
        run_id=retried.id,
    )
