"""Services for task-backed execution runs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.db import crud
from app.models.activity_events import ActivityEvent
from app.models.agents import Agent
from app.models.boards import Board
from app.models.silo_roles import SiloRole
from app.models.silos import Silo
from app.models.task_execution_runs import TaskExecutionRun
from app.models.tasks import Task
from app.schemas.task_execution_runs import (
    TaskExecutionRunCallback,
    TaskExecutionRunCreate,
    TaskExecutionRunRead,
    TaskExecutionRunUpdate,
)
from app.services.activity_log import record_activity
from app.services.approval_task_links import pending_approval_conflicts_by_task
from app.services.task_execution_dispatch import SymphonyDispatchAdapter


class TaskExecutionRunService:
    """Persist and update task-backed execution runs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_runs(
        self,
        *,
        organization_id: UUID,
        board_id: UUID,
        task_id: UUID,
    ) -> list[TaskExecutionRunRead]:
        """List execution runs for one task ordered newest-first."""
        rows = await self._session.exec(
            select(TaskExecutionRun, Silo)
            .join(Silo, col(Silo.id) == col(TaskExecutionRun.silo_id))
            .where(col(TaskExecutionRun.organization_id) == organization_id)
            .where(col(TaskExecutionRun.board_id) == board_id)
            .where(col(TaskExecutionRun.task_id) == task_id)
            .order_by(col(TaskExecutionRun.created_at).desc()),
        )
        return [self._to_read(run, silo_slug=silo.slug) for run, silo in rows.all()]

    async def get_run(
        self,
        *,
        organization_id: UUID,
        board_id: UUID,
        task_id: UUID,
        run_id: UUID,
    ) -> TaskExecutionRunRead | None:
        """Load one execution run scoped to a task."""
        row = await self._session.exec(
            select(TaskExecutionRun, Silo)
            .join(Silo, col(Silo.id) == col(TaskExecutionRun.silo_id))
            .where(col(TaskExecutionRun.organization_id) == organization_id)
            .where(col(TaskExecutionRun.board_id) == board_id)
            .where(col(TaskExecutionRun.task_id) == task_id)
            .where(col(TaskExecutionRun.id) == run_id),
        )
        result = row.first()
        if result is None:
            return None
        run, silo = result
        return self._to_read(run, silo_slug=silo.slug)

    async def create_run(
        self,
        *,
        board: Board,
        task: Task,
        payload: TaskExecutionRunCreate,
        requested_by_user_id: UUID | None = None,
        requested_by_agent_id: UUID | None = None,
    ) -> TaskExecutionRunRead:
        """Create a new queued execution run for a task."""
        silo = await crud.get_one_by(
            self._session,
            Silo,
            organization_id=board.organization_id,
            slug=payload.silo_slug,
        )
        if silo is None:
            raise ValueError("Silo not found")
        if not silo.enable_symphony:
            raise ValueError("Silo does not have Symphony enabled")
        if task.status == "done":
            raise ValueError("Done tasks cannot be dispatched to Symphony")

        role = await self._resolve_role(silo_id=silo.id, requested_role_slug=payload.role_slug)

        now = utcnow()
        run = TaskExecutionRun(
            organization_id=board.organization_id,
            board_id=board.id,
            task_id=task.id,
            silo_id=silo.id,
            requested_by_user_id=requested_by_user_id,
            requested_by_agent_id=requested_by_agent_id,
            executor_kind="symphony",
            role_slug=role.slug,
            status="queued",
            task_snapshot={
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
            },
            dispatch_payload={
                "silo_slug": silo.slug,
                "role_slug": role.slug,
                "prompt_override": payload.prompt_override,
                "branch_name_hint": payload.branch_name_hint,
                "input_metadata": payload.input_metadata,
            },
            created_at=now,
            updated_at=now,
        )
        self._session.add(run)
        record_activity(
            self._session,
            event_type="task.execution_run.created",
            message=self._build_created_message(
                run=run,
                silo_slug=silo.slug,
                role_slug=role.slug,
                dispatch_payload=run.dispatch_payload,
            ),
            payload=self._build_created_payload(
                run=run,
                silo_slug=silo.slug,
                role_slug=role.slug,
                dispatch_payload=run.dispatch_payload,
            ),
            task_id=task.id,
            board_id=board.id,
            agent_id=requested_by_agent_id,
        )
        await self._session.commit()
        await self._session.refresh(run)
        return self._to_read(run, silo_slug=silo.slug)

    async def update_run(
        self,
        *,
        organization_id: UUID,
        board: Board,
        task: Task,
        run_id: UUID,
        payload: TaskExecutionRunUpdate,
    ) -> TaskExecutionRunRead:
        """Update execution run status and result metadata."""
        run = await crud.get_one_by(
            self._session,
            TaskExecutionRun,
            organization_id=organization_id,
            board_id=board.id,
            task_id=task.id,
            id=run_id,
        )
        if run is None:
            raise ValueError("Execution run not found")

        if payload.status is not None:
            run.status = payload.status
            if payload.status == "running" and run.started_at is None:
                run.started_at = utcnow()
            if payload.status in {"succeeded", "failed", "cancelled", "blocked"}:
                run.completed_at = utcnow()

        for field_name in (
            "external_run_id",
            "workspace_path",
            "branch_name",
            "pr_url",
            "summary",
            "error_message",
        ):
            value = getattr(payload, field_name)
            if value is not None:
                setattr(run, field_name, value)

        if payload.result_payload is not None:
            run.result_payload = payload.result_payload

        run.updated_at = utcnow()
        self._session.add(run)
        silo = await self._session.get(Silo, run.silo_id)
        if silo is None:
            raise ValueError("Silo not found")

        if payload.status is not None:
            record_activity(
                self._session,
            event_type="task.execution_run.updated",
            message=self._build_updated_message(run=run, silo_slug=silo.slug),
            payload=self._build_run_payload(run=run, silo_slug=silo.slug),
            task_id=task.id,
            board_id=board.id,
        )

        await self._apply_callback_task_effects(
            board=board,
            task=task,
            run=run,
            payload=payload,
        )

        await self._session.commit()
        return self._to_read(run, silo_slug=silo.slug)

    async def retry_run(
        self,
        *,
        organization_id: UUID,
        board: Board,
        task: Task,
        run_id: UUID,
        requested_by_user_id: UUID | None = None,
        requested_by_agent_id: UUID | None = None,
    ) -> TaskExecutionRunRead:
        """Clone a prior execution run into a new queued run for retry."""
        run = await crud.get_one_by(
            self._session,
            TaskExecutionRun,
            organization_id=organization_id,
            board_id=board.id,
            task_id=task.id,
            id=run_id,
        )
        if run is None:
            raise ValueError("Execution run not found")
        if run.status not in {"failed", "cancelled", "blocked"}:
            raise ValueError("Only failed, cancelled, or blocked runs can be retried")

        dispatch_payload = run.dispatch_payload or {}
        silo = await self._session.get(Silo, run.silo_id)
        if silo is None:
            raise ValueError("Silo not found")
        retried = await self.create_run(
            board=board,
            task=task,
            payload=TaskExecutionRunCreate(
                silo_slug=silo.slug,
                role_slug=run.role_slug,
                prompt_override=(
                    dispatch_payload.get("prompt_override")
                    if isinstance(dispatch_payload.get("prompt_override"), str)
                    else None
                ),
                branch_name_hint=(
                    dispatch_payload.get("branch_name_hint")
                    if isinstance(dispatch_payload.get("branch_name_hint"), str)
                    else run.branch_name
                ),
                input_metadata=(
                    dispatch_payload.get("input_metadata")
                    if isinstance(dispatch_payload.get("input_metadata"), dict)
                    else {}
                ),
            ),
            requested_by_user_id=requested_by_user_id,
            requested_by_agent_id=requested_by_agent_id,
        )
        record_activity(
            self._session,
            event_type="task.execution_run.retried",
            message=self._build_retried_message(
                original_run=run,
                retried_run=retried,
                silo_slug=silo.slug,
                dispatch_payload=dispatch_payload,
            ),
            payload=self._build_retried_payload(
                original_run=run,
                retried_run=retried,
                silo_slug=silo.slug,
                dispatch_payload=dispatch_payload,
            ),
            task_id=task.id,
            board_id=board.id,
            agent_id=requested_by_agent_id,
        )
        await self._session.commit()
        return retried

    async def dispatch_run(
        self,
        *,
        organization_id: UUID,
        board_id: UUID,
        task_id: UUID,
        run_id: UUID,
        adapter: SymphonyDispatchAdapter | None = None,
    ) -> TaskExecutionRunRead:
        """Build and persist a Symphony dispatch contract for one queued run."""
        row = await self._session.exec(
            select(TaskExecutionRun, Task, Board, Silo, SiloRole)
            .join(Task, col(Task.id) == col(TaskExecutionRun.task_id))
            .join(Board, col(Board.id) == col(TaskExecutionRun.board_id))
            .join(Silo, col(Silo.id) == col(TaskExecutionRun.silo_id))
            .join(
                SiloRole,
                (col(SiloRole.silo_id) == col(Silo.id)) & (col(SiloRole.slug) == col(TaskExecutionRun.role_slug)),
            )
            .where(col(TaskExecutionRun.organization_id) == organization_id)
            .where(col(TaskExecutionRun.board_id) == board_id)
            .where(col(TaskExecutionRun.task_id) == task_id)
            .where(col(TaskExecutionRun.id) == run_id),
        )
        result = row.first()
        if result is None:
            raise ValueError("Execution run not found")
        run, task, board, silo, role = result
        if run.status not in {"queued", "blocked"}:
            return self._to_read(run, silo_slug=silo.slug)

        dispatch_adapter = adapter or SymphonyDispatchAdapter()
        request = dispatch_adapter.build_request(
            run=run,
            task=task,
            board=board,
            silo=silo,
            role=role,
        )
        acceptance = await dispatch_adapter.dispatch(request=request)
        now = utcnow()

        run.status = "dispatching"
        run.external_run_id = acceptance.external_run_id
        run.workspace_path = acceptance.workspace_path
        run.branch_name = acceptance.branch_name
        run.summary = acceptance.summary
        run.started_at = run.started_at or now
        run.result_payload = {
            "dispatch_request": dispatch_adapter.dump_request(request),
            "dispatch_acceptance": dispatch_adapter.dump_acceptance(acceptance),
        }
        run.updated_at = now
        self._session.add(run)
        record_activity(
            self._session,
            event_type="task.execution_run.dispatched",
            message=self._build_dispatched_message(
                run=run,
                silo_slug=silo.slug,
                adapter_mode=acceptance.adapter_mode,
            ),
            payload=self._build_dispatched_payload(
                run=run,
                silo_slug=silo.slug,
                adapter_mode=acceptance.adapter_mode,
            ),
            task_id=task.id,
            board_id=board.id,
        )
        await self._session.commit()
        return self._to_read(run, silo_slug=silo.slug)

    async def update_run_by_id(
        self,
        *,
        run_id: UUID,
        payload: TaskExecutionRunCallback,
    ) -> TaskExecutionRunRead:
        """Update one execution run by id for Symphony callbacks."""
        row = await self._session.exec(
            select(TaskExecutionRun, Task, Board, Silo)
            .join(Task, col(Task.id) == col(TaskExecutionRun.task_id))
            .join(Board, col(Board.id) == col(TaskExecutionRun.board_id))
            .join(Silo, col(Silo.id) == col(TaskExecutionRun.silo_id))
            .where(col(TaskExecutionRun.id) == run_id),
        )
        result = row.first()
        if result is None:
            raise ValueError("Execution run not found")
        run, task, board, _silo = result
        return await self.update_run(
            organization_id=run.organization_id,
            board=board,
            task=task,
            run_id=run.id,
            payload=TaskExecutionRunUpdate(
                status=payload.status,
                external_run_id=payload.external_run_id,
                workspace_path=payload.workspace_path,
                branch_name=payload.branch_name,
                pr_url=payload.pr_url,
                summary=payload.summary,
                error_message=payload.error_message,
                issue_identifier=payload.issue_identifier,
                completion_kind=payload.completion_kind,
                duration_ms=payload.duration_ms,
                result_payload=self._merge_callback_result_payload(payload=payload),
            ),
        )

    @staticmethod
    def _merge_callback_result_payload(
        *,
        payload: TaskExecutionRunCallback,
    ) -> dict[str, Any] | None:
        result_payload: dict[str, Any] = (
            dict(payload.result_payload) if isinstance(payload.result_payload, dict) else {}
        )
        if payload.issue_identifier is not None:
            result_payload["issue_identifier"] = payload.issue_identifier
        if payload.completion_kind is not None:
            result_payload["completion_kind"] = payload.completion_kind
        if payload.duration_ms is not None:
            result_payload["duration_ms"] = payload.duration_ms
        return result_payload or None

    async def _resolve_role(self, *, silo_id: UUID, requested_role_slug: str | None) -> SiloRole:
        role: SiloRole | None = None
        if requested_role_slug is not None:
            role = await crud.get_one_by(
                self._session,
                SiloRole,
                silo_id=silo_id,
                slug=requested_role_slug,
            )
            if role is None:
                raise ValueError("Silo role not found")
        else:
            row = await self._session.exec(
                select(SiloRole)
                .where(col(SiloRole.silo_id) == silo_id)
                .where(col(SiloRole.runtime_kind) == "symphony")
                .order_by(col(SiloRole.created_at).asc()),
            )
            role = row.first()
            if role is None:
                raise ValueError("Silo has no Symphony role")

        if role.runtime_kind != "symphony":
            raise ValueError("Silo role is not a Symphony runtime")
        return role

    async def _apply_callback_task_effects(
        self,
        *,
        board: Board,
        task: Task,
        run: TaskExecutionRun,
        payload: TaskExecutionRunUpdate,
    ) -> None:
        status = payload.status
        if status is None:
            return

        now = utcnow()

        if status == "running":
            if await self._can_auto_transition_task(board=board, task=task, target_status="in_progress"):
                previous_status = task.status
                task.status = "in_progress"
                task.in_progress_at = task.in_progress_at or now
                task.updated_at = now
                self._session.add(task)
                record_activity(
                    self._session,
                    event_type="task.status_changed",
                    message=f"Task moved to in_progress: {task.title}.",
                    payload={
                        "task_id": str(task.id),
                        "board_id": str(board.id),
                        "task_title": task.title,
                        "status": "in_progress",
                        "previous_status": previous_status,
                        "reason": "execution_run_running",
                    },
                    task_id=task.id,
                    board_id=board.id,
                )
            return

        report_message = self._build_callback_report(run=run, payload=payload)
        if report_message is not None:
            self._session.add(
                ActivityEvent(
                    event_type="task.execution_run.report",
                    message=report_message,
                    payload=self._build_callback_report_payload(
                        run=run,
                        payload=payload,
                    ),
                    task_id=task.id,
                    board_id=board.id,
                ),
            )

        if status != "succeeded":
            return

        if await self._can_auto_transition_task(board=board, task=task, target_status="review"):
            previous_status = task.status
            lead = await self._board_lead(board_id=board.id)
            task.previous_in_progress_at = task.in_progress_at
            task.in_progress_at = None
            task.status = "review"
            if lead is not None:
                task.assigned_agent_id = lead.id
            task.updated_at = now
            self._session.add(task)
            record_activity(
                self._session,
                event_type="task.status_changed",
                message=f"Task moved to review: {task.title}.",
                payload={
                    "task_id": str(task.id),
                    "board_id": str(board.id),
                    "task_title": task.title,
                    "status": "review",
                    "previous_status": previous_status,
                    "assigned_agent_id": str(lead.id) if lead is not None else None,
                    "reason": "execution_run_succeeded",
                },
                task_id=task.id,
                board_id=board.id,
            )

    async def _can_auto_transition_task(
        self,
        *,
        board: Board,
        task: Task,
        target_status: str,
    ) -> bool:
        if board.only_lead_can_change_status:
            return False
        if task.status == target_status:
            return False
        if task.status == "done":
            return False
        if target_status == "in_progress":
            return task.status == "inbox"
        if target_status != "review":
            return False
        if task.status not in {"inbox", "in_progress"}:
            return False
        if board.comment_required_for_review:
            return False
        if board.block_status_changes_with_pending_approval:
            conflicts = await pending_approval_conflicts_by_task(
                self._session,
                board_id=board.id,
                task_ids=[task.id],
            )
            if task.id in conflicts:
                return False
        return True

    async def _board_lead(self, *, board_id: UUID) -> Agent | None:
        row = await self._session.exec(
            select(Agent)
            .where(col(Agent.board_id) == board_id)
            .where(col(Agent.is_board_lead).is_(True))
            .order_by(col(Agent.created_at).asc())
        )
        return row.first()

    @staticmethod
    def _build_callback_report(
        *,
        run: TaskExecutionRun,
        payload: TaskExecutionRunUpdate,
    ) -> str | None:
        if payload.status not in {"succeeded", "failed", "cancelled", "blocked"}:
            return None

        lines: list[str] = [
            f"Symphony {payload.status} execution run `{TaskExecutionRunService._short_run_id(run.id)}`."
        ]
        if payload.summary:
            lines.append(payload.summary)
        pull_request = TaskExecutionRunService._extract_pull_request_number(
            payload.result_payload
        )
        if pull_request is not None:
            lines.append(f"PR #{pull_request}")
        if payload.pr_url:
            lines.append(f"PR: {payload.pr_url}")
        elif payload.branch_name:
            lines.append(f"Branch: {payload.branch_name}")
        total_tokens = TaskExecutionRunService._extract_total_tokens(
            payload.result_payload
        )
        if total_tokens is not None:
            lines.append(f"Tokens: {total_tokens}")
        if payload.error_message:
            lines.append(f"Error: {payload.error_message}")
        return "\n".join(lines)

    @staticmethod
    def _build_created_message(
        *,
        run: TaskExecutionRun,
        silo_slug: str,
        role_slug: str,
        dispatch_payload: dict[str, Any] | None,
    ) -> str:
        parts = [
            f"Queued Symphony run {TaskExecutionRunService._short_run_id(run.id)} for {silo_slug}/{role_slug}."
        ]
        branch_hint = TaskExecutionRunService._read_dispatch_text(
            dispatch_payload,
            "branch_name_hint",
        )
        if branch_hint:
            parts.append(f"Branch hint: {branch_hint}.")
        prompt_override = TaskExecutionRunService._read_dispatch_text(
            dispatch_payload,
            "prompt_override",
        )
        if prompt_override:
            parts.append("Prompt override attached.")
        return " ".join(parts)

    @staticmethod
    def _build_created_payload(
        *,
        run: TaskExecutionRun,
        silo_slug: str,
        role_slug: str,
        dispatch_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = TaskExecutionRunService._build_run_payload(run=run, silo_slug=silo_slug)
        branch_hint = TaskExecutionRunService._read_dispatch_text(
            dispatch_payload,
            "branch_name_hint",
        )
        if branch_hint:
            payload["branch_hint"] = branch_hint
        payload["has_prompt_override"] = bool(
            TaskExecutionRunService._read_dispatch_text(dispatch_payload, "prompt_override")
        )
        payload["role_slug"] = role_slug
        return payload

    @staticmethod
    def _build_retried_message(
        *,
        original_run: TaskExecutionRun,
        retried_run: TaskExecutionRunRead,
        silo_slug: str,
        dispatch_payload: dict[str, Any] | None,
    ) -> str:
        parts = [
            "Retried Symphony run",
            TaskExecutionRunService._short_run_id(original_run.id),
            "as",
            TaskExecutionRunService._short_run_id(retried_run.id),
            f"for {silo_slug}/{retried_run.role_slug}.",
        ]
        branch_hint = TaskExecutionRunService._read_dispatch_text(
            dispatch_payload,
            "branch_name_hint",
        )
        if branch_hint:
            parts.append(f"Branch hint: {branch_hint}.")
        return " ".join(parts)

    @staticmethod
    def _build_retried_payload(
        *,
        original_run: TaskExecutionRun,
        retried_run: TaskExecutionRunRead,
        silo_slug: str,
        dispatch_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = TaskExecutionRunService._build_read_payload(run=retried_run)
        payload["silo_slug"] = silo_slug
        payload["retried_from_run_id"] = str(original_run.id)
        branch_hint = TaskExecutionRunService._read_dispatch_text(
            dispatch_payload,
            "branch_name_hint",
        )
        if branch_hint:
            payload["branch_hint"] = branch_hint
        return payload

    @staticmethod
    def _build_dispatched_message(
        *,
        run: TaskExecutionRun,
        silo_slug: str,
        adapter_mode: str,
    ) -> str:
        parts = [
            f"Dispatched Symphony run {TaskExecutionRunService._short_run_id(run.id)} to {silo_slug}/{run.role_slug}",
            f"via {adapter_mode} adapter.",
        ]
        if run.external_run_id:
            parts.append(f"External run: {run.external_run_id}.")
        if run.branch_name:
            parts.append(f"Branch: {run.branch_name}.")
        if run.workspace_path:
            parts.append(f"Workspace: {run.workspace_path}.")
        return " ".join(parts)

    @staticmethod
    def _build_dispatched_payload(
        *,
        run: TaskExecutionRun,
        silo_slug: str,
        adapter_mode: str,
    ) -> dict[str, Any]:
        payload = TaskExecutionRunService._build_run_payload(run=run, silo_slug=silo_slug)
        payload["adapter_mode"] = adapter_mode
        return payload

    @staticmethod
    def _build_updated_message(*, run: TaskExecutionRun, silo_slug: str) -> str:
        parts = [
            f"Symphony run {TaskExecutionRunService._short_run_id(run.id)} is {run.status} on {silo_slug}/{run.role_slug}."
        ]
        if run.summary:
            parts.append(run.summary)
        pull_request = TaskExecutionRunService._extract_pull_request_number(
            run.result_payload
        )
        if pull_request is not None:
            parts.append(f"PR #{pull_request}.")
        if run.pr_url:
            parts.append(f"PR: {run.pr_url}")
        elif run.branch_name:
            parts.append(f"Branch: {run.branch_name}.")
        total_tokens = TaskExecutionRunService._extract_total_tokens(
            run.result_payload
        )
        if total_tokens is not None:
            parts.append(f"Tokens: {total_tokens}.")
        if run.error_message:
            parts.append(f"Error: {run.error_message}")
        return " ".join(parts)

    @staticmethod
    def _build_callback_report_payload(
        *,
        run: TaskExecutionRun,
        payload: TaskExecutionRunUpdate,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "executor_kind": "symphony",
            "run_id": str(run.id),
            "run_short_id": TaskExecutionRunService._short_run_id(run.id),
            "silo_id": str(run.silo_id),
            "role_slug": run.role_slug,
            "status": payload.status or run.status,
            "external_run_id": payload.external_run_id or run.external_run_id,
            "workspace_path": payload.workspace_path or run.workspace_path,
            "branch_name": payload.branch_name or run.branch_name,
            "pr_url": payload.pr_url or run.pr_url,
            "summary": payload.summary or run.summary,
            "error_message": payload.error_message or run.error_message,
        }
        pull_request = TaskExecutionRunService._extract_pull_request_number(
            payload.result_payload or run.result_payload
        )
        if pull_request is not None:
            result["pull_request"] = pull_request
        total_tokens = TaskExecutionRunService._extract_total_tokens(
            payload.result_payload or run.result_payload
        )
        if total_tokens is not None:
            result["total_tokens"] = total_tokens
        TaskExecutionRunService._merge_result_payload_metadata(
            result=result,
            result_payload=payload.result_payload or run.result_payload,
        )
        return result

    @staticmethod
    def _build_run_payload(
        *,
        run: TaskExecutionRun,
        silo_slug: str,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "executor_kind": "symphony",
            "run_id": str(run.id),
            "run_short_id": TaskExecutionRunService._short_run_id(run.id),
            "organization_id": str(run.organization_id),
            "board_id": str(run.board_id),
            "task_id": str(run.task_id),
            "silo_id": str(run.silo_id),
            "silo_slug": silo_slug,
            "role_slug": run.role_slug,
            "status": run.status,
        }
        if run.external_run_id:
            result["external_run_id"] = run.external_run_id
        if run.workspace_path:
            result["workspace_path"] = run.workspace_path
        if run.branch_name:
            result["branch_name"] = run.branch_name
        if run.pr_url:
            result["pr_url"] = run.pr_url
        if run.summary:
            result["summary"] = run.summary
        if run.error_message:
            result["error_message"] = run.error_message
        pull_request = TaskExecutionRunService._extract_pull_request_number(run.result_payload)
        if pull_request is not None:
            result["pull_request"] = pull_request
        total_tokens = TaskExecutionRunService._extract_total_tokens(run.result_payload)
        if total_tokens is not None:
            result["total_tokens"] = total_tokens
        TaskExecutionRunService._merge_result_payload_metadata(
            result=result,
            result_payload=run.result_payload,
        )
        return result

    @staticmethod
    def _build_read_payload(run: TaskExecutionRunRead) -> dict[str, Any]:
        result: dict[str, Any] = {
            "executor_kind": run.executor_kind,
            "run_id": str(run.id),
            "run_short_id": TaskExecutionRunService._short_run_id(run.id),
            "organization_id": str(run.organization_id),
            "board_id": str(run.board_id),
            "task_id": str(run.task_id),
            "silo_id": str(run.silo_id),
            "silo_slug": run.silo_slug,
            "role_slug": run.role_slug,
            "status": run.status,
        }
        if run.external_run_id:
            result["external_run_id"] = run.external_run_id
        if run.workspace_path:
            result["workspace_path"] = run.workspace_path
        if run.branch_name:
            result["branch_name"] = run.branch_name
        if run.pr_url:
            result["pr_url"] = run.pr_url
        if run.summary:
            result["summary"] = run.summary
        if run.error_message:
            result["error_message"] = run.error_message
        pull_request = TaskExecutionRunService._extract_pull_request_number(run.result_payload)
        if pull_request is not None:
            result["pull_request"] = pull_request
        total_tokens = TaskExecutionRunService._extract_total_tokens(run.result_payload)
        if total_tokens is not None:
            result["total_tokens"] = total_tokens
        return result

    @staticmethod
    def _read_dispatch_text(
        dispatch_payload: dict[str, Any] | None,
        key: str,
    ) -> str | None:
        if not isinstance(dispatch_payload, dict):
            return None
        value = dispatch_payload.get(key)
        if not isinstance(value, str):
            return None
        trimmed = value.strip()
        return trimmed or None

    @staticmethod
    def _short_run_id(run_id: UUID | str) -> str:
        return str(run_id)[:8]

    @staticmethod
    def _extract_pull_request_number(
        result_payload: dict[str, Any] | None,
    ) -> int | None:
        if not isinstance(result_payload, dict):
            return None
        value = result_payload.get("pull_request")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed.isdigit():
                return int(trimmed)
        return None

    @staticmethod
    def _extract_total_tokens(
        result_payload: dict[str, Any] | None,
    ) -> int | None:
        if not isinstance(result_payload, dict):
            return None
        usage = result_payload.get("usage")
        if not isinstance(usage, dict):
            return None
        value = usage.get("total_tokens")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed.isdigit():
                return int(trimmed)
        return None

    @staticmethod
    def _extract_result_text(
        result_payload: dict[str, Any] | None,
        key: str,
    ) -> str | None:
        if not isinstance(result_payload, dict):
            return None
        value = result_payload.get(key)
        if not isinstance(value, str):
            return None
        trimmed = value.strip()
        return trimmed or None

    @staticmethod
    def _extract_result_int(
        result_payload: dict[str, Any] | None,
        key: str,
    ) -> int | None:
        if not isinstance(result_payload, dict):
            return None
        value = result_payload.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed.lstrip("-").isdigit():
                return int(trimmed)
        return None

    @staticmethod
    def _merge_result_payload_metadata(
        *,
        result: dict[str, Any],
        result_payload: dict[str, Any] | None,
    ) -> None:
        text_keys = (
            "issue_identifier",
            "runner_kind",
            "completion_kind",
            "last_event",
            "last_message",
            "session_id",
        )
        int_keys = (
            "turn_count",
            "duration_ms",
        )
        for key in text_keys:
            value = TaskExecutionRunService._extract_result_text(result_payload, key)
            if value is not None:
                result[key] = value
        for key in int_keys:
            value = TaskExecutionRunService._extract_result_int(result_payload, key)
            if value is not None:
                result[key] = value

    @staticmethod
    def _to_read(run: TaskExecutionRun, *, silo_slug: str) -> TaskExecutionRunRead:
        return TaskExecutionRunRead(
            id=run.id,
            organization_id=run.organization_id,
            board_id=run.board_id,
            task_id=run.task_id,
            silo_id=run.silo_id,
            silo_slug=silo_slug,
            requested_by_user_id=run.requested_by_user_id,
            requested_by_agent_id=run.requested_by_agent_id,
            executor_kind="symphony",
            role_slug=run.role_slug,
            status=run.status,
            task_snapshot=run.task_snapshot,
            dispatch_payload=run.dispatch_payload,
            result_payload=run.result_payload,
            external_run_id=run.external_run_id,
            workspace_path=run.workspace_path,
            branch_name=run.branch_name,
            pr_url=run.pr_url,
            summary=run.summary,
            error_message=run.error_message,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
