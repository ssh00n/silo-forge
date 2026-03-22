"""Typed wrappers around shared execution contract schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.contracts.generated_schemas import (
    ACTIVITY__EXECUTION_RUN_PAYLOAD_SCHEMA_JSON,
    ACTIVITY_EXECUTION_RUN_PAYLOAD_EXECUTOR_KIND,
    ACTIVITY_EXECUTION_RUN_PAYLOAD_STATUS,
    EXECUTION__CALLBACK_PAYLOAD_SCHEMA_JSON,
    EXECUTION_CALLBACK_PAYLOAD_STATUS,
)
from app.contracts.json_schema import validate_contract_payload

ExecutionRunStatus = EXECUTION_CALLBACK_PAYLOAD_STATUS
ExecutionRunExecutorKind = ACTIVITY_EXECUTION_RUN_PAYLOAD_EXECUTOR_KIND

ExecutionCallbackSchema = EXECUTION__CALLBACK_PAYLOAD_SCHEMA_JSON
ExecutionRunActivitySchema = ACTIVITY__EXECUTION_RUN_PAYLOAD_SCHEMA_JSON


class ExecutionCallbackResultPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    issue_identifier: str | None = None
    runner_kind: str | None = None
    completion_kind: str | None = None
    failure_reason: str | None = None
    block_reason: str | None = None
    cancel_reason: str | None = None
    stall_reason: str | None = None
    last_event: str | None = None
    last_message: str | None = None
    session_id: str | None = None
    turn_count: int | None = None
    duration_ms: int | None = None
    pull_request: int | None = None
    usage: dict[str, Any] | None = None


class ExecutionCallbackContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ExecutionRunStatus
    external_run_id: str | None = None
    workspace_path: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    summary: str | None = None
    error_message: str | None = None
    issue_identifier: str | None = None
    completion_kind: str | None = None
    duration_ms: int | None = None
    result_payload: ExecutionCallbackResultPayload | None = None


class ExecutionRunActivityPayloadContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executor_kind: ExecutionRunExecutorKind
    run_id: str
    run_short_id: str
    organization_id: str | None = None
    board_id: str | None = None
    task_id: str | None = None
    silo_id: str
    silo_slug: str | None = None
    role_slug: str
    status: ACTIVITY_EXECUTION_RUN_PAYLOAD_STATUS
    adapter_mode: str | None = None
    branch_hint: str | None = None
    branch_name: str | None = None
    workspace_path: str | None = None
    external_run_id: str | None = None
    summary: str | None = None
    pr_url: str | None = None
    pull_request: int | None = None
    total_tokens: int | None = None
    error_message: str | None = None
    issue_identifier: str | None = None
    runner_kind: str | None = None
    completion_kind: str | None = None
    failure_reason: str | None = None
    block_reason: str | None = None
    cancel_reason: str | None = None
    stall_reason: str | None = None
    last_event: str | None = None
    last_message: str | None = None
    session_id: str | None = None
    turn_count: int | None = None
    duration_ms: int | None = None
    has_prompt_override: bool | None = None
    retried_from_run_id: str | None = None


def parse_execution_callback_contract(payload: Any) -> ExecutionCallbackContract:
    validate_contract_payload(schema=ExecutionCallbackSchema, payload=payload)
    return ExecutionCallbackContract.model_validate(payload)


def finalize_execution_run_activity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: value for key, value in payload.items() if value is not None}
    validate_contract_payload(schema=ExecutionRunActivitySchema, payload=normalized)
    return ExecutionRunActivityPayloadContract.model_validate(normalized).model_dump(
        exclude_none=True
    )
