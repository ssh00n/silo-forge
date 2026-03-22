from __future__ import annotations

from uuid import uuid4

from app.core.time import utcnow
from app.services.queue import QueuedTask, _decode_task


def test_queued_task_to_json_and_decode_use_contract_envelope() -> None:
    created_at = utcnow()
    task = QueuedTask(
        task_type="task_execution_dispatch",
        payload={
            "organization_id": str(uuid4()),
            "board_id": str(uuid4()),
            "task_id": str(uuid4()),
            "run_id": str(uuid4()),
        },
        created_at=created_at,
        attempts=3,
    )

    raw = task.to_json()
    decoded = _decode_task(raw, "default")

    assert decoded.task_type == "task_execution_dispatch"
    assert decoded.payload == task.payload
    assert decoded.created_at == created_at
    assert decoded.attempts == 3
