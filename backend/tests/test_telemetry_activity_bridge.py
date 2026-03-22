# ruff: noqa: INP001
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.time import utcnow
from app.services.queue import QueuedTask
from app.services import queue_worker
from app.services.webhooks import dispatch
from app.services.webhooks.queue import QueuedInboundDelivery


@pytest.mark.asyncio
async def test_queue_worker_persists_activity_for_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = QueuedTask(
        task_type="task_execution_dispatch",
        payload={
            "organization_id": str(uuid4()),
            "board_id": str(uuid4()),
            "task_id": str(uuid4()),
            "run_id": str(uuid4()),
        },
        created_at=utcnow(),
        attempts=1,
    )
    dequeued = [task, None]
    recorded: list[tuple[str, dict[str, object], object | None]] = []

    def _fake_dequeue(
        queue_name: str,
        *,
        redis_url: str | None = None,
        block: bool = False,
        block_timeout: float = 0,
    ) -> QueuedTask | None:
        del queue_name, redis_url, block, block_timeout
        return dequeued.pop(0)

    async def _fake_handler(_: QueuedTask) -> None:
        return None

    async def _fake_record(
        *,
        event_type: str,
        payload: dict[str, object],
        board_id: object | None = None,
    ) -> None:
        recorded.append((event_type, payload, board_id))

    monkeypatch.setattr("app.services.queue_worker.dequeue_task", _fake_dequeue)
    monkeypatch.setitem(
        queue_worker._TASK_HANDLERS,
        "task_execution_dispatch",
        queue_worker._TaskHandler(
            handler=_fake_handler,
            attempts_to_delay=lambda attempts: 1.0,
            requeue=lambda queued, delay: True,
        ),
    )
    monkeypatch.setattr("app.services.queue_worker.record_telemetry_activity", _fake_record)
    monkeypatch.setattr("app.services.queue_worker.settings.rq_dispatch_throttle_seconds", 0)

    await queue_worker.flush_queue()

    assert recorded[0][0] == "queue.worker.success"
    assert recorded[0][1]["status"] == "succeeded"
    assert recorded[-1][0] == "queue.worker.batch_complete"


@pytest.mark.asyncio
async def test_webhook_dispatch_persists_activity_for_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = QueuedInboundDelivery(
        board_id=uuid4(),
        webhook_id=uuid4(),
        payload_id=uuid4(),
        received_at=datetime.now(UTC),
        attempts=0,
    )
    recorded: list[tuple[str, dict[str, object], object | None]] = []

    async def _fake_process(_: QueuedInboundDelivery) -> None:
        return None

    async def _fake_record(
        *,
        event_type: str,
        payload: dict[str, object],
        board_id: object | None = None,
    ) -> None:
        recorded.append((event_type, payload, board_id))

    monkeypatch.setattr(dispatch, "_process_single_item", _fake_process)
    monkeypatch.setattr(dispatch, "record_telemetry_activity", _fake_record)
    monkeypatch.setattr(dispatch.settings, "rq_dispatch_throttle_seconds", 0)
    monkeypatch.setattr(dispatch.time, "sleep", lambda seconds: None)

    calls = [item, None]
    monkeypatch.setattr(dispatch, "dequeue_webhook_delivery", lambda: calls.pop(0))

    await dispatch.flush_webhook_delivery_queue()

    assert recorded[0][0] == "webhook.dispatch.success"
    assert recorded[0][1]["status"] == "succeeded"
    assert recorded[0][2] == item.board_id
    assert recorded[-1][0] == "webhook.dispatch.batch_complete"
