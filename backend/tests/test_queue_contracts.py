from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.time import utcnow
from app.services.openclaw.lifecycle_queue import QueuedAgentLifecycleReconcile
from app.services.task_execution_queue import (
    QueuedTaskExecutionDispatch,
    decode_task_execution_dispatch_task,
    enqueue_task_execution_dispatch,
)
from app.services.queue import QueuedTask
from app.services.webhooks.queue import QueuedInboundDelivery, decode_webhook_task


def test_enqueue_task_execution_dispatch_emits_contract_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_enqueue(task: QueuedTask, queue_name: str, *, redis_url: str | None = None) -> bool:
        captured["task"] = task
        captured["queue_name"] = queue_name
        captured["redis_url"] = redis_url
        return True

    monkeypatch.setattr("app.services.task_execution_queue.enqueue_task", _fake_enqueue)
    payload = QueuedTaskExecutionDispatch(
        organization_id=uuid4(),
        board_id=uuid4(),
        task_id=uuid4(),
        run_id=uuid4(),
    )

    assert enqueue_task_execution_dispatch(payload) is True
    task = captured["task"]
    assert isinstance(task, QueuedTask)
    assert task.payload == {
        "organization_id": str(payload.organization_id),
        "board_id": str(payload.board_id),
        "task_id": str(payload.task_id),
        "run_id": str(payload.run_id),
    }


def test_decode_task_execution_dispatch_task_roundtrip() -> None:
    organization_id = uuid4()
    board_id = uuid4()
    task_id = uuid4()
    run_id = uuid4()
    task = QueuedTask(
        task_type="task_execution_dispatch",
        payload={
            "organization_id": str(organization_id),
            "board_id": str(board_id),
            "task_id": str(task_id),
            "run_id": str(run_id),
        },
        created_at=utcnow(),
        attempts=2,
    )

    decoded = decode_task_execution_dispatch_task(task)
    assert decoded.organization_id == organization_id
    assert decoded.board_id == board_id
    assert decoded.task_id == task_id
    assert decoded.run_id == run_id
    assert decoded.attempts == 2


def test_decode_webhook_task_accepts_contract_payload_shape() -> None:
    received_at = datetime.now(UTC).replace(microsecond=0)
    task = QueuedTask(
        task_type="webhook_delivery",
        payload={
            "board_id": str(uuid4()),
            "webhook_id": str(uuid4()),
            "payload_id": str(uuid4()),
            "received_at": received_at.isoformat(),
        },
        created_at=received_at,
        attempts=1,
    )

    decoded = decode_webhook_task(task)
    assert decoded.received_at == received_at
    assert decoded.attempts == 1


def test_lifecycle_contract_payload_shape_roundtrip() -> None:
    payload = QueuedAgentLifecycleReconcile(
        agent_id=uuid4(),
        gateway_id=uuid4(),
        board_id=uuid4(),
        generation=4,
        checkin_deadline_at=utcnow() + timedelta(minutes=2),
        attempts=1,
    )
    task = QueuedTask(
        task_type="agent_lifecycle_reconcile",
        payload={
            "agent_id": str(payload.agent_id),
            "gateway_id": str(payload.gateway_id),
            "board_id": str(payload.board_id),
            "generation": payload.generation,
            "checkin_deadline_at": payload.checkin_deadline_at.isoformat(),
        },
        created_at=utcnow(),
        attempts=payload.attempts,
    )

    from app.services.openclaw.lifecycle_queue import decode_lifecycle_task

    decoded = decode_lifecycle_task(task)
    assert decoded.agent_id == payload.agent_id
    assert decoded.gateway_id == payload.gateway_id
    assert decoded.board_id == payload.board_id
    assert decoded.generation == payload.generation
