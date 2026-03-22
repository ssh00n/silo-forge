from __future__ import annotations

import pytest

from app.contracts.execution import (
    finalize_execution_run_activity_payload,
    parse_execution_callback_contract,
)
from app.contracts.json_schema import ContractValidationError


def test_parse_execution_callback_contract_accepts_rich_payload() -> None:
    contract = parse_execution_callback_contract(
        {
            "status": "succeeded",
            "external_run_id": "mc-run-1",
            "summary": "Completed successfully.",
            "issue_identifier": "MC-123",
            "completion_kind": "completed",
            "duration_ms": 4200,
            "result_payload": {
                "issue_identifier": "MC-123",
                "completion_kind": "completed",
                "last_event": "turn.completed",
                "turn_count": 1,
                "duration_ms": 4200,
                "usage": {"total_tokens": 144},
            },
        }
    )
    assert contract.status == "succeeded"
    assert contract.result_payload is not None
    assert contract.result_payload.turn_count == 1


def test_finalize_execution_run_activity_payload_rejects_unknown_fields() -> None:
    with pytest.raises(ContractValidationError):
        finalize_execution_run_activity_payload(
            {
                "executor_kind": "symphony",
                "run_id": "run-1",
                "run_short_id": "run-1",
                "silo_id": "silo-1",
                "role_slug": "symphony",
                "status": "queued",
                "unexpected": "nope",
            }
        )


def test_finalize_execution_run_activity_payload_normalizes_valid_payload() -> None:
    payload = finalize_execution_run_activity_payload(
        {
            "executor_kind": "symphony",
            "run_id": "run-1",
            "run_short_id": "run-1",
            "organization_id": "org-1",
            "board_id": "board-1",
            "task_id": "task-1",
            "silo_id": "silo-1",
            "silo_slug": "demo-silo",
            "role_slug": "symphony",
            "status": "running",
            "summary": "Worker session started.",
            "duration_ms": 3000,
        }
    )
    assert payload["status"] == "running"
    assert payload["duration_ms"] == 3000
    assert payload["silo_slug"] == "demo-silo"
