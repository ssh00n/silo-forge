"""Typed wrappers around shared queue payload contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.contracts.generated_schemas import (
    QUEUE__AGENT_LIFECYCLE_RECONCILE_PAYLOAD_SCHEMA_JSON,
    QUEUE__TASK_ENVELOPE_SCHEMA_JSON,
    QUEUE__TASK_EXECUTION_DISPATCH_PAYLOAD_SCHEMA_JSON,
    QUEUE__WEBHOOK_DELIVERY_PAYLOAD_SCHEMA_JSON,
)
from app.contracts.json_schema import validate_contract_payload


class TaskExecutionDispatchQueuePayloadContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str
    board_id: str
    task_id: str
    run_id: str


class WebhookDeliveryQueuePayloadContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    board_id: str
    webhook_id: str
    payload_id: str
    received_at: datetime


class AgentLifecycleReconcileQueuePayloadContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    gateway_id: str
    board_id: str | None = None
    generation: int
    checkin_deadline_at: datetime


class QueuedTaskEnvelopeContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: str
    payload: dict[str, Any]
    created_at: datetime
    attempts: int = 0


def parse_queued_task_envelope(payload: dict[str, Any]) -> QueuedTaskEnvelopeContract:
    validate_contract_payload(schema=QUEUE__TASK_ENVELOPE_SCHEMA_JSON, payload=payload)
    return QueuedTaskEnvelopeContract.model_validate(payload)


def finalize_queued_task_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    return parse_queued_task_envelope(payload).model_dump(mode="json")


def parse_task_execution_dispatch_queue_payload(
    payload: dict[str, Any],
) -> TaskExecutionDispatchQueuePayloadContract:
    validate_contract_payload(
        schema=QUEUE__TASK_EXECUTION_DISPATCH_PAYLOAD_SCHEMA_JSON, payload=payload
    )
    return TaskExecutionDispatchQueuePayloadContract.model_validate(payload)


def finalize_task_execution_dispatch_queue_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return parse_task_execution_dispatch_queue_payload(payload).model_dump()


def parse_webhook_delivery_queue_payload(
    payload: dict[str, Any],
) -> WebhookDeliveryQueuePayloadContract:
    validate_contract_payload(schema=QUEUE__WEBHOOK_DELIVERY_PAYLOAD_SCHEMA_JSON, payload=payload)
    return WebhookDeliveryQueuePayloadContract.model_validate(payload)


def finalize_webhook_delivery_queue_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return parse_webhook_delivery_queue_payload(payload).model_dump(mode="json")


def parse_agent_lifecycle_reconcile_queue_payload(
    payload: dict[str, Any],
) -> AgentLifecycleReconcileQueuePayloadContract:
    validate_contract_payload(
        schema=QUEUE__AGENT_LIFECYCLE_RECONCILE_PAYLOAD_SCHEMA_JSON,
        payload=payload,
    )
    return AgentLifecycleReconcileQueuePayloadContract.model_validate(payload)


def finalize_agent_lifecycle_reconcile_queue_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return parse_agent_lifecycle_reconcile_queue_payload(payload).model_dump(mode="json")
