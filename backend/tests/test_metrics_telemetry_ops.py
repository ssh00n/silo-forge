from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from app.api import metrics as metrics_api
from app.models.activity_events import ActivityEvent


class _ExecFirstResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def first(self) -> object | None:
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
async def test_telemetry_ops_metrics_maps_worker_and_webhook_snapshots() -> None:
    board_id = uuid4()
    task_id = uuid4()
    worker_recent = ActivityEvent(
        event_type="queue.worker.success",
        board_id=board_id,
        task_id=task_id,
        payload={
            "queue_name": "default",
            "task_type": "task_execution_dispatch",
            "attempt": 0,
        },
        created_at=datetime(2026, 3, 22, 9, 10, 0),
    )
    webhook_recent = ActivityEvent(
        event_type="webhook.dispatch.failed",
        board_id=board_id,
        payload={
            "payload_id": str(uuid4()),
            "delivery_attempt": 2,
        },
        created_at=datetime(2026, 3, 22, 9, 12, 0),
    )
    session = _SequentialSession(
        [
            _ExecFirstResult(worker_recent),
            _ExecFirstResult(webhook_recent),
            _ExecAllResult(
                [
                    ("queue.worker.success", 5),
                    ("queue.worker.failed", 1),
                    ("queue.worker.dequeue_failed", 2),
                ]
            ),
            _ExecAllResult(
                [
                    ("webhook.dispatch.success", 8),
                    ("webhook.dispatch.failed", 3),
                    ("webhook.dispatch.requeued", 4),
                ]
            ),
        ]
    )

    snapshot = await metrics_api._telemetry_ops_metrics(
        session,
        metrics_api._resolve_range("7d"),
        [board_id],
    )

    assert snapshot.worker.latest_event_type == "queue.worker.success"
    assert snapshot.worker.latest_queue_name == "default"
    assert snapshot.worker.latest_task_type == "task_execution_dispatch"
    assert snapshot.worker.latest_attempt == 0
    assert snapshot.worker.latest_board_id == board_id
    assert snapshot.worker.latest_task_id == task_id
    assert snapshot.worker.success_count_7d == 5
    assert snapshot.worker.failure_count_7d == 1
    assert snapshot.worker.dequeue_failure_count_7d == 2

    assert snapshot.webhook.latest_event_type == "webhook.dispatch.failed"
    assert snapshot.webhook.latest_attempt == 2
    assert snapshot.webhook.latest_board_id == board_id
    assert snapshot.webhook.success_count_7d == 8
    assert snapshot.webhook.failure_count_7d == 3
    assert snapshot.webhook.retried_count_7d == 4
