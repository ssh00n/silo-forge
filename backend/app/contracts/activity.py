"""Typed wrappers around shared activity payload contracts."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict

from app.contracts.generated_schemas import (
    ACTIVITY__APPROVAL_PAYLOAD_SCHEMA_JSON,
    ACTIVITY__BOARD_PAYLOAD_SCHEMA_JSON,
    ACTIVITY__GATEWAY_PAYLOAD_SCHEMA_JSON,
    ACTIVITY__TASK_PAYLOAD_SCHEMA_JSON,
)
from app.contracts.json_schema import validate_contract_payload

_ActivityContractT = TypeVar("_ActivityContractT", bound=BaseModel)


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


class BoardActivityPayloadContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_kind: str
    notification_status: str
    board_id: str
    board_name: str
    target_agent_id: str
    target_agent_name: str
    source_board_id: str | None = None
    source_board_name: str | None = None
    board_group_id: str | None = None
    board_group_name: str | None = None
    changed_fields: list[str] | None = None
    error: str | None = None


class GatewayActivityPayloadContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_kind: str
    notification_status: str
    board_id: str | None = None
    board_name: str | None = None
    actor_agent_id: str | None = None
    target_agent_id: str | None = None
    target_agent_name: str | None = None
    gateway_id: str | None = None
    gateway_name: str | None = None
    action: str | None = None
    delivery_status: str | None = None
    target_kind: str | None = None
    workspace_path: str | None = None
    session_key: str | None = None
    error: str | None = None


def _parse_activity_payload(
    *,
    schema: dict[str, Any],
    payload: dict[str, Any],
    model: type[_ActivityContractT],
) -> _ActivityContractT:
    validate_contract_payload(schema=schema, payload=payload)
    return model.model_validate(payload)


def _finalize_activity_payload(
    *,
    schema: dict[str, Any],
    payload: dict[str, Any],
    model: type[_ActivityContractT],
) -> dict[str, Any]:
    return _parse_activity_payload(schema=schema, payload=payload, model=model).model_dump(
        exclude_unset=True
    )


def parse_task_activity_payload(payload: dict[str, Any]) -> TaskActivityPayloadContract:
    return _parse_activity_payload(
        schema=ACTIVITY__TASK_PAYLOAD_SCHEMA_JSON,
        payload=payload,
        model=TaskActivityPayloadContract,
    )


def finalize_task_activity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _finalize_activity_payload(
        schema=ACTIVITY__TASK_PAYLOAD_SCHEMA_JSON,
        payload=payload,
        model=TaskActivityPayloadContract,
    )


def parse_approval_activity_payload(payload: dict[str, Any]) -> ApprovalActivityPayloadContract:
    return _parse_activity_payload(
        schema=ACTIVITY__APPROVAL_PAYLOAD_SCHEMA_JSON,
        payload=payload,
        model=ApprovalActivityPayloadContract,
    )


def finalize_approval_activity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _finalize_activity_payload(
        schema=ACTIVITY__APPROVAL_PAYLOAD_SCHEMA_JSON,
        payload=payload,
        model=ApprovalActivityPayloadContract,
    )


def parse_board_activity_payload(payload: dict[str, Any]) -> BoardActivityPayloadContract:
    return _parse_activity_payload(
        schema=ACTIVITY__BOARD_PAYLOAD_SCHEMA_JSON,
        payload=payload,
        model=BoardActivityPayloadContract,
    )


def finalize_board_activity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _finalize_activity_payload(
        schema=ACTIVITY__BOARD_PAYLOAD_SCHEMA_JSON,
        payload=payload,
        model=BoardActivityPayloadContract,
    )


def parse_gateway_activity_payload(payload: dict[str, Any]) -> GatewayActivityPayloadContract:
    return _parse_activity_payload(
        schema=ACTIVITY__GATEWAY_PAYLOAD_SCHEMA_JSON,
        payload=payload,
        model=GatewayActivityPayloadContract,
    )


def finalize_gateway_activity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _finalize_activity_payload(
        schema=ACTIVITY__GATEWAY_PAYLOAD_SCHEMA_JSON,
        payload=payload,
        model=GatewayActivityPayloadContract,
    )
