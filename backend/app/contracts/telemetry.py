"""Typed wrappers around shared telemetry contract schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.contracts.generated_schemas import (
    TELEMETRY__QUEUE_WORKER_EVENT_PAYLOAD_SCHEMA_JSON,
    TELEMETRY__WEBHOOK_DELIVERY_RESULT_PAYLOAD_SCHEMA_JSON,
)
from app.contracts.json_schema import validate_contract_payload


class QueueWorkerEventTelemetryContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_name: str
    status: str
    task_type: str | None = None
    attempt: int | None = None
    error: str | None = None
    count: int | None = None
    throttle_seconds: float | None = None
    retry_delay_seconds: float | None = None


class WebhookDeliveryResultTelemetryContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    board_id: str | None = None
    webhook_id: str | None = None
    payload_id: str | None = None
    attempt: int
    status: str
    error: str | None = None
    retry_delay_seconds: float | None = None
    count: int | None = None
    duration_ms: int | None = None
    throttle_seconds: float | None = None


def parse_queue_worker_event_payload(payload: dict[str, Any]) -> QueueWorkerEventTelemetryContract:
    validate_contract_payload(
        schema=TELEMETRY__QUEUE_WORKER_EVENT_PAYLOAD_SCHEMA_JSON, payload=payload
    )
    return QueueWorkerEventTelemetryContract.model_validate(payload)


def finalize_queue_worker_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if "error" in normalized and normalized["error"] is not None:
        normalized["error"] = str(normalized["error"])
    return parse_queue_worker_event_payload(normalized).model_dump(mode="json", exclude_none=True)


def parse_webhook_delivery_result_payload(
    payload: dict[str, Any],
) -> WebhookDeliveryResultTelemetryContract:
    validate_contract_payload(
        schema=TELEMETRY__WEBHOOK_DELIVERY_RESULT_PAYLOAD_SCHEMA_JSON,
        payload=payload,
    )
    return WebhookDeliveryResultTelemetryContract.model_validate(payload)


def finalize_webhook_delivery_result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if "error" in normalized and normalized["error"] is not None:
        normalized["error"] = str(normalized["error"])
    return parse_webhook_delivery_result_payload(normalized).model_dump(
        mode="json", exclude_none=True
    )
