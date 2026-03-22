"""Dashboard metrics schemas for KPI and time-series API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlmodel import SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)
DashboardRangeKey = Literal["24h", "3d", "7d", "14d", "1m", "3m", "6m", "1y"]
DashboardBucketKey = Literal["hour", "day", "week", "month"]


class DashboardSeriesPoint(SQLModel):
    """Single numeric time-series point."""

    period: datetime
    value: float


class DashboardWipPoint(SQLModel):
    """Work-in-progress point split by task status buckets."""

    period: datetime
    inbox: int
    in_progress: int
    review: int
    done: int


class DashboardRangeSeries(SQLModel):
    """Series payload for a single range/bucket combination."""

    range: DashboardRangeKey
    bucket: DashboardBucketKey
    points: list[DashboardSeriesPoint]


class DashboardWipRangeSeries(SQLModel):
    """WIP series payload for a single range/bucket combination."""

    range: DashboardRangeKey
    bucket: DashboardBucketKey
    points: list[DashboardWipPoint]


class DashboardSeriesSet(SQLModel):
    """Primary vs comparison pair for generic series metrics."""

    primary: DashboardRangeSeries
    comparison: DashboardRangeSeries


class DashboardWipSeriesSet(SQLModel):
    """Primary vs comparison pair for WIP status series metrics."""

    primary: DashboardWipRangeSeries
    comparison: DashboardWipRangeSeries


class DashboardKpis(SQLModel):
    """Topline dashboard KPI summary values."""

    active_agents: int
    tasks_in_progress: int
    inbox_tasks: int
    in_progress_tasks: int
    review_tasks: int
    done_tasks: int
    error_rate_pct: float
    median_cycle_time_hours_7d: float | None


class DashboardPendingApproval(SQLModel):
    """Single pending approval item for cross-board dashboard listing."""

    approval_id: UUID
    board_id: UUID
    board_name: str
    action_type: str
    confidence: float
    created_at: datetime
    task_title: str | None = None


class DashboardPendingApprovals(SQLModel):
    """Pending approval snapshot used on the dashboard."""

    total: int
    items: list[DashboardPendingApproval]


class DashboardRuntimeRunRead(SQLModel):
    """Recent task execution runtime row for dashboard visibility."""

    run_id: UUID
    board_id: UUID
    board_name: str
    task_id: UUID
    task_title: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime
    summary: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class DashboardRuntimeExecutionMetrics(SQLModel):
    """Execution-runtime snapshot used by the dashboard."""

    generated_at: datetime
    queued_runs: int
    active_runs: int
    failed_runs_7d: int
    succeeded_runs_7d: int
    input_tokens_7d: int
    output_tokens_7d: int
    total_tokens_7d: int
    recent_runs: list[DashboardRuntimeRunRead]


class DashboardTelemetryWorkerMetrics(SQLModel):
    """Queue worker telemetry snapshot used by the dashboard."""

    latest_event_type: str | None = None
    latest_at: datetime | None = None
    latest_queue_name: str | None = None
    latest_task_type: str | None = None
    latest_attempt: int | None = None
    latest_board_id: UUID | None = None
    latest_task_id: UUID | None = None
    success_count_7d: int = 0
    failure_count_7d: int = 0
    dequeue_failure_count_7d: int = 0


class DashboardTelemetryWebhookMetrics(SQLModel):
    """Webhook telemetry snapshot used by the dashboard."""

    latest_event_type: str | None = None
    latest_at: datetime | None = None
    latest_payload_id: str | None = None
    latest_attempt: int | None = None
    latest_board_id: UUID | None = None
    success_count_7d: int = 0
    failure_count_7d: int = 0
    retried_count_7d: int = 0


class DashboardTelemetryOpsMetrics(SQLModel):
    """Operational telemetry snapshot used by the dashboard."""

    generated_at: datetime
    worker: DashboardTelemetryWorkerMetrics
    webhook: DashboardTelemetryWebhookMetrics


class DashboardMetrics(SQLModel):
    """Complete dashboard metrics response payload."""

    range: DashboardRangeKey
    generated_at: datetime
    kpis: DashboardKpis
    throughput: DashboardSeriesSet
    cycle_time: DashboardSeriesSet
    error_rate: DashboardSeriesSet
    wip: DashboardWipSeriesSet
    pending_approvals: DashboardPendingApprovals
