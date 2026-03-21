from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from app.api import metrics as metrics_api
from app.models.boards import Board
from app.models.task_execution_runs import TaskExecutionRun
from app.models.tasks import Task


class _ExecOneResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def one(self) -> int:
        return self._value


class _ExecAllResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _SequentialSession:
    def __init__(self, responses: list[object]) -> None:
        self._responses = responses
        self._index = 0

    async def exec(self, _statement: object) -> object:
        response = self._responses[self._index]
        self._index += 1
        return response


@pytest.mark.asyncio
async def test_runtime_execution_metrics_maps_recent_runs_and_usage() -> None:
    board_id = uuid4()
    task_id = uuid4()
    run_id = uuid4()
    board = Board(id=board_id, organization_id=uuid4(), name="Delivery", slug="delivery")
    task = Task(id=task_id, board_id=board_id, title="Wire runtime dashboard")
    run = TaskExecutionRun(
        id=run_id,
        organization_id=board.organization_id,
        board_id=board_id,
        task_id=task_id,
        silo_id=uuid4(),
        role_slug="symphony",
        status="succeeded",
        summary="Opened PR with dashboard metrics.",
        pr_url="https://github.com/example/repo/pull/9",
        branch_name="feature/runtime-metrics",
        result_payload={
            "usage": {
                "input_tokens": 120,
                "output_tokens": 80,
                "total_tokens": 200,
            }
        },
        created_at=datetime(2026, 3, 21, 11, 45, 0),
        started_at=datetime(2026, 3, 21, 11, 50, 0),
        completed_at=datetime(2026, 3, 21, 12, 0, 0),
        updated_at=datetime(2026, 3, 21, 12, 0, 0),
    )
    session = _SequentialSession(
        [
            _ExecOneResult(2),
            _ExecOneResult(1),
            _ExecAllResult([(run, task, board)]),
            _ExecAllResult([run]),
        ]
    )
    range_spec = metrics_api._resolve_range("7d")

    snapshot = await metrics_api._runtime_execution_metrics(session, range_spec, [board_id], limit=8)

    assert snapshot.queued_runs == 2
    assert snapshot.active_runs == 1
    assert snapshot.succeeded_runs_7d == 1
    assert snapshot.failed_runs_7d == 0
    assert snapshot.total_tokens_7d == 200
    assert len(snapshot.recent_runs) == 1
    recent = snapshot.recent_runs[0]
    assert recent.run_id == run_id
    assert recent.task_title == "Wire runtime dashboard"
    assert recent.board_name == "Delivery"
    assert recent.total_tokens == 200
    assert recent.pr_url == "https://github.com/example/repo/pull/9"
    assert recent.created_at == datetime(2026, 3, 21, 11, 45, 0)
    assert recent.started_at == datetime(2026, 3, 21, 11, 50, 0)
    assert recent.completed_at == datetime(2026, 3, 21, 12, 0, 0)
