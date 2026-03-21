"""Symphony-dispatch contract builders for Mission Control task execution runs."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from uuid import UUID

import httpx

from app.core.config import settings
from app.models.boards import Board
from app.models.silo_roles import SiloRole
from app.models.silos import Silo
from app.models.task_execution_runs import TaskExecutionRun
from app.models.tasks import Task

_BRANCH_SANITIZER_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class SymphonyIssueContract:
    """Mission Control task normalized into Symphony issue shape."""

    id: str
    identifier: str
    title: str
    description: str | None
    priority: int | None
    state: str
    branch_name: str | None
    url: str | None
    labels: list[str]
    blocked_by: list[dict[str, str | None]]
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class SymphonyDispatchRequest:
    """Stub dispatch request handed off by Mission Control."""

    execution_run_id: str
    silo_slug: str
    role_slug: str
    workspace_root: str
    callback_url: str
    issue: SymphonyIssueContract
    prompt_override: str | None
    adapter_mode: str = "stub"


@dataclass(frozen=True)
class SymphonyDispatchAcceptance:
    """Dispatch acceptance returned by the control-plane stub adapter."""

    accepted: bool
    adapter_mode: str
    external_run_id: str
    workspace_path: str
    branch_name: str
    summary: str


class SymphonyDispatchAdapter:
    """Build a Symphony-compatible contract and return a stub acceptance."""

    def __init__(
        self,
        *,
        bridge_base_url: str | None = None,
        bridge_token: str | None = None,
    ) -> None:
        self._bridge_base_url = (
            bridge_base_url.strip().rstrip("/")
            if bridge_base_url is not None
            else settings.symphony_bridge_base_url
        )
        self._bridge_token = bridge_token.strip() if bridge_token is not None else settings.symphony_bridge_token

    def build_request(
        self,
        *,
        run: TaskExecutionRun,
        task: Task,
        board: Board,
        silo: Silo,
        role: SiloRole,
    ) -> SymphonyDispatchRequest:
        """Build the normalized dispatch request for one execution run."""
        branch_name = self._branch_name(run=run, task=task, board=board)
        workspace_root = role.workspace_root or "~/symphony"
        issue = SymphonyIssueContract(
            id=str(task.id),
            identifier=f"MC-{str(task.id)[:8]}",
            title=task.title,
            description=task.description,
            priority=self._priority(task.priority),
            state=task.status,
            branch_name=branch_name,
            url=f"{settings.base_url}/boards/{board.id}/tasks/{task.id}",
            labels=[
                f"board:{board.slug}",
                f"silo:{silo.slug}",
                f"role:{role.slug}",
            ],
            blocked_by=[],
            created_at=task.created_at.isoformat() if task.created_at else None,
            updated_at=task.updated_at.isoformat() if task.updated_at else None,
        )
        prompt_override = None
        if run.dispatch_payload and isinstance(run.dispatch_payload, dict):
            raw_prompt = run.dispatch_payload.get("prompt_override")
            prompt_override = raw_prompt if isinstance(raw_prompt, str) and raw_prompt.strip() else None
        return SymphonyDispatchRequest(
            execution_run_id=str(run.id),
            silo_slug=silo.slug,
            role_slug=role.slug,
            workspace_root=workspace_root,
            callback_url=(
                f"{settings.base_url}/api/v1/task-execution-runs/{run.id}/callbacks/symphony"
            ),
            issue=issue,
            prompt_override=prompt_override,
            adapter_mode="http" if self._bridge_base_url else "stub",
        )

    async def dispatch(
        self,
        *,
        request: SymphonyDispatchRequest,
    ) -> SymphonyDispatchAcceptance:
        """Dispatch to an HTTP bridge when configured, otherwise return stub acceptance."""
        if self._bridge_base_url:
            headers: dict[str, str] = {}
            if self._bridge_token:
                headers["Authorization"] = f"Bearer {self._bridge_token}"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._bridge_base_url}/api/v1/mission-control/dispatches",
                    json=self.dump_request(request),
                    headers=headers,
                )
            response.raise_for_status()
            body = response.json()
            return SymphonyDispatchAcceptance(
                accepted=bool(body.get("accepted", True)),
                adapter_mode="http",
                external_run_id=str(body.get("external_run_id") or f"mc-{request.execution_run_id}"),
                workspace_path=str(
                    body.get("workspace_path")
                    or f"{request.workspace_root.rstrip('/')}/mission-control/{request.issue.identifier}"
                ),
                branch_name=str(body.get("branch_name") or request.issue.branch_name or "task/dispatch"),
                summary=str(
                    body.get("summary")
                    or "Mission Control dispatched execution to the Symphony bridge."
                ),
            )
        workspace_path = (
            f"{request.workspace_root.rstrip('/')}/mission-control/{request.issue.identifier}"
        )
        return SymphonyDispatchAcceptance(
            accepted=True,
            adapter_mode=request.adapter_mode,
            external_run_id=f"mc-{request.execution_run_id}",
            workspace_path=workspace_path,
            branch_name=request.issue.branch_name or "task/dispatch",
            summary="Mission Control prepared a Symphony-compatible dispatch contract.",
        )

    def dump_request(self, request: SymphonyDispatchRequest) -> dict[str, object]:
        """Serialize the dispatch request to JSON-compatible data."""
        data = asdict(request)
        data["issue"] = asdict(request.issue)
        return data

    def dump_acceptance(self, acceptance: SymphonyDispatchAcceptance) -> dict[str, object]:
        """Serialize the dispatch acceptance to JSON-compatible data."""
        return asdict(acceptance)

    def _branch_name(self, *, run: TaskExecutionRun, task: Task, board: Board) -> str:
        if run.branch_name:
            return run.branch_name
        if run.dispatch_payload and isinstance(run.dispatch_payload, dict):
            hint = run.dispatch_payload.get("branch_name_hint")
            if isinstance(hint, str) and hint.strip():
                return hint.strip()
        board_slug = _sanitize(board.slug or "board")
        title_slug = _sanitize(task.title or "task")
        return f"task/{board_slug}/{title_slug[:48]}".rstrip("/")

    @staticmethod
    def _priority(priority: str) -> int | None:
        mapping = {"low": 4, "medium": 3, "high": 2, "urgent": 1}
        return mapping.get(priority.strip().lower()) if priority else None


def _sanitize(value: str) -> str:
    return _BRANCH_SANITIZER_RE.sub("-", value.strip().lower()).strip("-") or "task"
