# ruff: noqa: INP001
from __future__ import annotations

from app.contracts.telemetry import (
    finalize_queue_worker_event_payload,
    finalize_webhook_delivery_result_payload,
)


def test_finalize_queue_worker_event_payload_normalizes_error() -> None:
    payload = finalize_queue_worker_event_payload(
        {
            "queue_name": "default",
            "status": "failed",
            "task_type": "task_execution_dispatch",
            "attempt": 2,
            "error": RuntimeError("boom"),
            "retry_delay_seconds": 5.5,
        }
    )

    assert payload == {
        "queue_name": "default",
        "status": "failed",
        "task_type": "task_execution_dispatch",
        "attempt": 2,
        "error": "boom",
        "retry_delay_seconds": 5.5,
    }


def test_finalize_webhook_delivery_result_payload_allows_batch_event_shape() -> None:
    payload = finalize_webhook_delivery_result_payload(
        {
            "board_id": None,
            "webhook_id": None,
            "payload_id": None,
            "attempt": 0,
            "status": "batch_finished",
            "duration_ms": 1234,
        }
    )

    assert payload == {
        "attempt": 0,
        "status": "batch_finished",
        "duration_ms": 1234,
    }
