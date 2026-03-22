"""Typed wrappers around shared activity payload contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.contracts.generated_schemas import (
    ACTIVITY__APPROVAL_PAYLOAD_SCHEMA_JSON,
    ACTIVITY__TASK_PAYLOAD_SCHEMA_JSON,
)
from app.contracts.json_schema import validate_contract_payload


class TaskActivityPayloadContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    board_id: str
    task_title: str
    status: str
    assigned_agent_id: str | None = None
    priority: str | int | None = None
    previous_status: str | None = None
    reason: str | None = None
    dependency_task_id: str | None = None
    dependency_task_title: str | None = None
    dependency_task_status: str | None = None
    target_agent_id: str | None = None
    target_agent_name: str | None = None
    notification_kind: str | None = None
    notification_status: str | None = None
    error: str | None = None


class ApprovalActivityPayloadContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    board_id: str
    task_id: str | None = None
    agent_id: str | None = None
    action_type: str
    approval_status: str
    notification_status: str
    lead_agent_id: str | None = None
    error: str | None = None


def finalize_task_activity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    validate_contract_payload(schema=ACTIVITY__TASK_PAYLOAD_SCHEMA_JSON, payload=payload)
    return TaskActivityPayloadContract.model_validate(payload).model_dump(exclude_unset=True)


def finalize_approval_activity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    validate_contract_payload(schema=ACTIVITY__APPROVAL_PAYLOAD_SCHEMA_JSON, payload=payload)
    return ApprovalActivityPayloadContract.model_validate(payload).model_dump(exclude_unset=True)
