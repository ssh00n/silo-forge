"""Symphony callback APIs for task execution runs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.config import settings
from app.db.session import get_session
from app.schemas.task_execution_runs import TaskExecutionRunCallback, TaskExecutionRunRead
from app.services.task_execution_runs import TaskExecutionRunService

router = APIRouter(prefix="/task-execution-runs", tags=["task-execution"])
SESSION_DEP = Depends(get_session)


def _require_symphony_callback_auth(
    x_symphony_token: str | None = Header(default=None, alias="X-Symphony-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    expected = settings.symphony_callback_token or settings.symphony_bridge_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Symphony callback auth is not configured",
        )

    token = (x_symphony_token or "").strip()
    if not token and authorization:
        value = authorization.strip()
        if value.lower().startswith("bearer "):
            token = value.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Symphony token")


CALLBACK_AUTH_DEP = Depends(_require_symphony_callback_auth)


@router.post("/{run_id}/callbacks/symphony", response_model=TaskExecutionRunRead)
async def receive_symphony_execution_callback(
    run_id: UUID,
    payload: TaskExecutionRunCallback,
    _auth=CALLBACK_AUTH_DEP,
    session=SESSION_DEP,
) -> TaskExecutionRunRead:
    """Receive execution status updates from a Symphony bridge."""
    try:
        return await TaskExecutionRunService(session).update_run_by_id(run_id=run_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
