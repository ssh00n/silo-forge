"use client";

export const dynamic = "force-dynamic";

import {
  type KeyboardEvent,
  type MouseEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { SignedIn, SignedOut, useAuth } from "@/auth/clerk";
import {
  Activity,
  ArrowUpRight,
  Bot,
  Info,
  LayoutGrid,
  Shield,
  Timer,
} from "lucide-react";

import { RuntimeRunMetaGrid } from "@/components/boards/RuntimeRunMetaGrid";
import { RuntimeRunStatusChip } from "@/components/boards/RuntimeRunStatusChip";
import { DashboardSidebar } from "@/components/organisms/DashboardSidebar";
import { DashboardShell } from "@/components/templates/DashboardShell";
import { Markdown } from "@/components/atoms/Markdown";
import { SignedOutPanel } from "@/components/auth/SignedOutPanel";
import { ApiError, customFetch } from "@/api/mutator";
import {
  type dashboardMetricsApiV1MetricsDashboardGetResponse,
  useDashboardMetricsApiV1MetricsDashboardGet,
} from "@/api/generated/metrics/metrics";
import {
  gatewaysStatusApiV1GatewaysStatusGet,
} from "@/api/generated/gateways/gateways";
import type { GatewaysStatusResponse } from "@/api/generated/model/gatewaysStatusResponse";
import {
  type listAgentsApiV1AgentsGetResponse,
  useListAgentsApiV1AgentsGet,
} from "@/api/generated/agents/agents";
import {
  type listBoardsApiV1BoardsGetResponse,
  useListBoardsApiV1BoardsGet,
} from "@/api/generated/boards/boards";
import {
  type listActivityApiV1ActivityGetResponse,
  useListActivityApiV1ActivityGet,
} from "@/api/generated/activity/activity";
import type { ActivityEventRead } from "@/api/generated/model";
import {
  activityCategoryForEvent,
  type ActivityCategory,
  resolveActivityFeedContent,
} from "@/lib/activity-events";
import {
  formatRelativeTimestamp,
  formatTimestamp,
  parseTimestamp,
} from "@/lib/formatters";
import {
  canAcknowledgeRuntimeRun,
  canCancelRuntimeRun,
  canEscalateRuntimeRun,
  canRetryRuntimeRun,
  formatRuntimeDurationMs,
  runtimeRunNeedsApprovalAttention,
  runtimeRunOperatorState,
  type RuntimeRunSnapshot,
  runtimeRunOperatorGuidance,
  runtimeRunTimingLabel,
} from "@/lib/runtime-runs";
import {
  buildDashboardSiloHealthViewModel,
} from "@/lib/silo-ops";
import {
  describeSiloRequestPressure,
  fetchSiloSpawnRequests,
  isOpenSiloRequestStatus,
} from "@/lib/silo-spawn-requests";
import { fetchSilos } from "@/lib/silos";
import { cn } from "@/lib/utils";

type SessionSummary = {
  key: string;
  title: string;
  subtitle: string;
  usage: string;
  lastSeenAt: string | null;
  isMain: boolean;
};

type SummaryRow = {
  label: string;
  value: string;
  tone?: "default" | "success" | "warning" | "danger";
};

type TelemetrySummary = {
  badge?: { text: string; tone: "online" | "offline" | "neutral" };
  rows: SummaryRow[];
};

type GatewayTarget = {
  gatewayId: string;
  boardId: string;
  boardName: string;
};

type GatewaySnapshot = GatewayTarget & {
  connected: boolean;
  gatewayUrl: string | null;
  sessionsCount: number;
  sessions: unknown[];
  mainSession: unknown | null;
  mainSessionError: string | null;
  error: string | null;
  requestError: string | null;
};

type DashboardRuntimeRunSnapshot = RuntimeRunSnapshot & {
  run_id: string;
  board_name: string;
  task_title: string;
  silo_id: string;
  silo_slug: string;
  silo_name: string;
  issue_identifier?: string | null;
  runner_kind?: string | null;
  completion_kind?: string | null;
  latest_approval_status?: string | null;
  latest_approval_resolved_at?: string | null;
  pending_approval_count?: number;
  last_event?: string | null;
  last_message?: string | null;
  session_id?: string | null;
  turn_count?: number | null;
  duration_ms?: number | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
};

type RuntimeMetricsSnapshot = {
  generated_at: string;
  queued_runs: number;
  active_runs: number;
  failed_runs_7d: number;
  succeeded_runs_7d: number;
  input_tokens_7d: number;
  output_tokens_7d: number;
  total_tokens_7d: number;
  recent_runs: DashboardRuntimeRunSnapshot[];
};

type RuntimeMetricsResponse = {
  data: RuntimeMetricsSnapshot;
  status: number;
  headers: Headers;
};

type DashboardAssignmentSummary = {
  siloSlug: string;
  siloName: string;
  activeCount: number;
  blockedCount: number;
  latestTaskTitle: string;
  latestBoardName: string;
};

type TelemetryOpsSnapshot = {
  generated_at: string;
  worker: {
    latest_event_type: string | null;
    latest_at: string | null;
    latest_queue_name: string | null;
    latest_task_type: string | null;
    latest_attempt: number | null;
    latest_board_id: string | null;
    latest_task_id: string | null;
    success_count_7d: number;
    failure_count_7d: number;
    dequeue_failure_count_7d: number;
  };
  webhook: {
    latest_event_type: string | null;
    latest_at: string | null;
    latest_payload_id: string | null;
    latest_attempt: number | null;
    latest_board_id: string | null;
    success_count_7d: number;
    failure_count_7d: number;
    retried_count_7d: number;
  };
};

type TelemetryOpsResponse = {
  data: TelemetryOpsSnapshot;
  status: number;
  headers: Headers;
};

type SiloRequestsSummary = {
  openCount: number;
  urgentCount: number;
  highCount: number;
  materializedRecentCount: number;
  demandLinkedCount: number;
  activeWorkloadCount: number;
};

type StreamedActivityEvent = ActivityEventRead;

  const DASH = "—";
const DASHBOARD_RANGE = "7d";
const DASHBOARD_RANGE_DAYS = 7;
const DASHBOARD_RANGE_LABEL = "7 days";
const DASHBOARD_ACTIVITY_FILTERS: Array<{
  value: ActivityCategory | "runtime";
  label: string;
}> = [
  { value: "all", label: "All" },
  { value: "runtime", label: "Runtime" },
  { value: "tasks", label: "Tasks" },
  { value: "approvals", label: "Approvals" },
  { value: "agents", label: "Agents" },
  { value: "boards", label: "Boards" },
  { value: "gateway", label: "Gateway" },
];

const dashboardActivityLabel = (eventType: string): string => {
  if (eventType === "task.execution_run.created") return "Run queued";
  if (eventType === "task.execution_run.dispatched") return "Run sent";
  if (eventType === "task.execution_run.retried") return "Run retried";
  if (eventType === "task.execution_run.updated") return "Run update";
  if (eventType === "task.execution_run.report") return "Run report";
  if (eventType === "silo.request.created") return "Request created";
  if (eventType === "silo.request.planned") return "Request planned";
  if (eventType === "silo.request.cancelled") return "Request cancelled";
  if (eventType === "silo.request.materialized") return "Request materialized";
  if (eventType.startsWith("silo.request.")) return "Silo request";
  if (eventType === "silo.runtime.validate") return "Runtime validate";
  if (eventType === "silo.runtime.apply") return "Runtime apply";
  if (eventType === "queue.worker.batch_started") return "Worker start";
  if (eventType === "queue.worker.batch_complete") return "Worker batch";
  if (eventType === "queue.worker.stopped") return "Worker stopped";
  if (eventType === "queue.worker.success") return "Worker success";
  if (eventType === "queue.worker.failed") return "Worker failed";
  if (eventType.startsWith("queue.worker.")) return "Worker";
  if (eventType === "webhook.dispatch.batch_started") return "Webhook batch";
  if (eventType === "webhook.dispatch.batch_complete") return "Webhook batch";
  if (eventType === "webhook.dispatch.batch_finished") return "Webhook finished";
  if (eventType === "webhook.dispatch.success") return "Webhook sent";
  if (eventType === "webhook.dispatch.failed") return "Webhook failed";
  if (eventType === "webhook.dispatch.requeued") return "Webhook retried";
  if (eventType.startsWith("webhook.dispatch.")) return "Webhook";
  if (eventType === "task.status_changed") return "Status";
  if (eventType === "task.created") return "Created";
  if (eventType === "approval.created") return "Approval";
  if (eventType === "approval.updated") return "Approval update";
  if (eventType === "approval.approved") return "Approved";
  if (eventType === "approval.rejected") return "Rejected";
  if (eventType.startsWith("agent.") && eventType.endsWith(".failed")) return "Lifecycle failed";
  if (eventType.startsWith("agent.") && eventType.endsWith(".direct")) return "Lifecycle";
  if (eventType === "agent.heartbeat") return "Heartbeat";
  if (eventType === "agent.wakeup.sent") return "Wakeup";
  if (eventType === "agent.nudge.sent") return "Nudge";
  if (eventType === "agent.nudge.failed") return "Nudge failed";
  if (eventType === "agent.soul.updated") return "SOUL updated";
  if (eventType.startsWith("gateway.")) return "Gateway";
  if (eventType.startsWith("board.")) return "Board";
  if (eventType.startsWith("task.")) return "Task";
  return eventType;
};

const dashboardActivityPillClass = (eventType: string): string => {
  if (eventType === "task.execution_run.created") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (eventType === "task.execution_run.dispatched") {
    return "border-indigo-200 bg-indigo-50 text-indigo-700";
  }
  if (eventType === "task.execution_run.retried") {
    return "border-orange-200 bg-orange-50 text-orange-700";
  }
  if (eventType === "task.execution_run.updated") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  if (eventType === "task.execution_run.report") {
    return "border-cyan-200 bg-cyan-50 text-cyan-700";
  }
  if (eventType === "silo.request.created" || eventType === "silo.request.planned") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  if (eventType === "silo.request.materialized") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (eventType === "silo.request.cancelled") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (eventType.startsWith("silo.request.")) {
    return "border-slate-200 bg-slate-100 text-slate-700";
  }
  if (eventType === "silo.runtime.validate") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  if (eventType === "silo.runtime.apply") {
    return "border-indigo-200 bg-indigo-50 text-indigo-700";
  }
  if (eventType === "queue.worker.success" || eventType === "queue.worker.batch_complete") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (eventType === "queue.worker.failed" || eventType === "queue.worker.dequeue_failed") {
    return "border-rose-200 bg-rose-50 text-rose-700";
  }
  if (eventType.startsWith("queue.worker.")) {
    return "border-slate-200 bg-slate-100 text-slate-700";
  }
  if (eventType === "webhook.dispatch.success" || eventType === "webhook.dispatch.batch_complete") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (eventType === "webhook.dispatch.failed") {
    return "border-rose-200 bg-rose-50 text-rose-700";
  }
  if (eventType === "webhook.dispatch.requeued") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (eventType.startsWith("webhook.dispatch.")) {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  const category = activityCategoryForEvent(eventType);
  if (category === "runtime" || category === "runs") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  if (category === "gateway") {
    return "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700";
  }
  if (category === "agents") {
    return "border-violet-200 bg-violet-50 text-violet-700";
  }
  if (category === "approvals") {
    return "border-cyan-200 bg-cyan-50 text-cyan-700";
  }
  if (category === "tasks") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-slate-200 bg-slate-100 text-slate-700";
};

const toRelativeOrDash = (value: string | null | undefined): string => {
  if (!value) return DASH;
  return formatRelativeTimestamp(value);
};

const toCountString = (value: unknown): string => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return formatCount(value);
  }
  return DASH;
};

const toTextOrDash = (value: unknown): string => {
  if (typeof value === "string" && value.trim().length > 0) {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return DASH;
};

const buildWorkerTelemetrySummary = (
  events: ActivityEventRead[],
  snapshot: TelemetryOpsSnapshot | null,
): TelemetrySummary => {
  if (snapshot) {
    const latest = snapshot.worker.latest_event_type;
    const failureTotal =
      snapshot.worker.failure_count_7d + snapshot.worker.dequeue_failure_count_7d;
    return {
      badge: {
        text: latest ? dashboardActivityLabel(latest) : "No signal",
        tone:
          latest === "queue.worker.failed" || latest === "queue.worker.dequeue_failed"
            ? "offline"
            : latest
              ? "online"
              : "neutral",
      },
      rows: [
        {
          label: "Latest event",
          value: snapshot.worker.latest_at
            ? toRelativeOrDash(snapshot.worker.latest_at)
            : "No worker activity",
          tone: snapshot.worker.latest_at ? "default" : "warning",
        },
        {
          label: "Successful jobs",
          value: toCountString(snapshot.worker.success_count_7d),
          tone: snapshot.worker.success_count_7d > 0 ? "success" : "default",
        },
        {
          label: "Worker failures",
          value: toCountString(failureTotal),
          tone: failureTotal > 0 ? "danger" : "default",
        },
        {
          label: "Queue",
          value: toTextOrDash(snapshot.worker.latest_queue_name),
        },
        {
          label: "Task type",
          value: toTextOrDash(snapshot.worker.latest_task_type),
        },
      ],
    };
  }
  const workerEvents = events.filter((event) => event.event_type.startsWith("queue.worker."));
  const latest = workerEvents[0];
  const payload = (latest?.payload ?? {}) as Record<string, unknown>;
  const failures = workerEvents.filter((event) =>
    event.event_type === "queue.worker.failed" || event.event_type === "queue.worker.dequeue_failed"
  ).length;
  const successes = workerEvents.filter((event) => event.event_type === "queue.worker.success").length;

  const badgeTone =
    latest?.event_type === "queue.worker.failed" || latest?.event_type === "queue.worker.dequeue_failed"
      ? "offline"
      : latest
        ? "online"
        : "neutral";
  const badgeText = latest ? dashboardActivityLabel(latest.event_type) : "No signal";

  return {
    badge: { text: badgeText, tone: badgeTone },
    rows: [
      {
        label: "Latest event",
        value: latest ? toRelativeOrDash(latest.created_at) : "No worker activity",
        tone: latest ? "default" : "warning",
      },
      {
        label: "Successful jobs",
        value: toCountString(successes),
        tone: successes > 0 ? "success" : "default",
      },
      {
        label: "Worker failures",
        value: toCountString(failures),
        tone: failures > 0 ? "danger" : "default",
      },
      {
        label: "Queue",
        value: toTextOrDash(payload.queue_name),
      },
      {
        label: "Task type",
        value: toTextOrDash(payload.task_type),
      },
    ],
  };
};

const buildWebhookTelemetrySummary = (
  events: ActivityEventRead[],
  snapshot: TelemetryOpsSnapshot | null,
): TelemetrySummary => {
  if (snapshot) {
    const latest = snapshot.webhook.latest_event_type;
    return {
      badge: {
        text: latest ? dashboardActivityLabel(latest) : "No signal",
        tone: latest === "webhook.dispatch.failed" ? "offline" : latest ? "online" : "neutral",
      },
      rows: [
        {
          label: "Latest event",
          value: snapshot.webhook.latest_at
            ? toRelativeOrDash(snapshot.webhook.latest_at)
            : "No webhook activity",
          tone: snapshot.webhook.latest_at ? "default" : "warning",
        },
        {
          label: "Delivered",
          value: toCountString(snapshot.webhook.success_count_7d),
          tone: snapshot.webhook.success_count_7d > 0 ? "success" : "default",
        },
        {
          label: "Failed",
          value: toCountString(snapshot.webhook.failure_count_7d),
          tone: snapshot.webhook.failure_count_7d > 0 ? "danger" : "default",
        },
        {
          label: "Retried",
          value: toCountString(snapshot.webhook.retried_count_7d),
          tone: snapshot.webhook.retried_count_7d > 0 ? "warning" : "default",
        },
        {
          label: "Attempts",
          value: toTextOrDash(snapshot.webhook.latest_attempt),
        },
      ],
    };
  }
  const webhookEvents = events.filter((event) => event.event_type.startsWith("webhook.dispatch."));
  const latest = webhookEvents[0];
  const payload = (latest?.payload ?? {}) as Record<string, unknown>;
  const sent = webhookEvents.filter((event) => event.event_type === "webhook.dispatch.success").length;
  const failed = webhookEvents.filter((event) => event.event_type === "webhook.dispatch.failed").length;
  const retried = webhookEvents.filter((event) => event.event_type === "webhook.dispatch.requeued").length;

  const badgeTone =
    latest?.event_type === "webhook.dispatch.failed"
      ? "offline"
      : latest
        ? "online"
        : "neutral";
  const badgeText = latest ? dashboardActivityLabel(latest.event_type) : "No signal";

  return {
    badge: { text: badgeText, tone: badgeTone },
    rows: [
      {
        label: "Latest event",
        value: latest ? toRelativeOrDash(latest.created_at) : "No webhook activity",
        tone: latest ? "default" : "warning",
      },
      {
        label: "Delivered",
        value: toCountString(sent),
        tone: sent > 0 ? "success" : "default",
      },
      {
        label: "Failed",
        value: toCountString(failed),
        tone: failed > 0 ? "danger" : "default",
      },
      {
        label: "Retried",
        value: toCountString(retried),
        tone: retried > 0 ? "warning" : "default",
      },
      {
        label: "Attempts",
        value: toTextOrDash(payload.attempt ?? payload.delivery_attempt ?? payload.attempts),
      },
    ],
  };
};

const latestActivityTimestamp = (items: ActivityEventRead[]): string | null => {
  let latestTime = 0;
  items.forEach((item) => {
    const value = parseTimestamp(item.created_at)?.getTime() ?? 0;
    if (value > latestTime) latestTime = value;
  });
  return latestTime ? new Date(latestTime).toISOString() : null;
};

const numberFormatter = new Intl.NumberFormat("en-US");
const SESSION_ID_KEYS = ["key", "id", "session_key", "sessionKey", "sessionId"];

const toRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || Array.isArray(value) || typeof value !== "object") return null;
  return value as Record<string, unknown>;
};

const readString = (
  record: Record<string, unknown> | null,
  keys: string[],
): string | null => {
  if (!record) return null;
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return null;
};

const readNumber = (
  record: Record<string, unknown> | null,
  keys: string[],
): number | null => {
  if (!record) return null;
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string") {
      const cleaned = value.replace(/[^0-9.-]/g, "");
      const parsed = Number.parseFloat(cleaned);
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return null;
};

const readStringFromRecords = (
  records: Array<Record<string, unknown> | null>,
  keys: string[],
): string | null => {
  for (const record of records) {
    const value = readString(record, keys);
    if (value) return value;
  }
  return null;
};

const readNumberFromRecords = (
  records: Array<Record<string, unknown> | null>,
  keys: string[],
): number | null => {
  for (const record of records) {
    const value = readNumber(record, keys);
    if (value !== null) return value;
  }
  return null;
};

const normalizeEpochMs = (value: number): number => {
  if (value >= 1_000_000_000_000) return value;
  if (value >= 1_000_000_000) return value * 1000;
  return value;
};

const readTimestamp = (
  record: Record<string, unknown> | null,
  keys: string[],
): string | null => {
  if (!record) return null;
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      const date = new Date(normalizeEpochMs(value));
      if (!Number.isNaN(date.getTime())) return date.toISOString();
    }
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (!trimmed) continue;
      const numeric = Number.parseFloat(trimmed);
      if (Number.isFinite(numeric)) {
        const date = new Date(normalizeEpochMs(numeric));
        if (!Number.isNaN(date.getTime())) return date.toISOString();
      }
      const parsed = parseTimestamp(trimmed);
      if (parsed) return parsed.toISOString();
    }
  }
  return null;
};

const readTimestampFromRecords = (
  records: Array<Record<string, unknown> | null>,
  keys: string[],
): string | null => {
  for (const record of records) {
    const value = readTimestamp(record, keys);
    if (value) return value;
  }
  return null;
};

const sessionIdentifiers = (record: Record<string, unknown> | null): string[] => {
  if (!record) return [];
  const ids = SESSION_ID_KEYS.map((key) => readString(record, [key])).filter(Boolean) as string[];
  return [...new Set(ids)];
};

const sharesSessionIdentity = (left: string[], right: string[]): boolean =>
  left.some((value) => right.includes(value));

const compactNumber = (value: number): string => {
  if (!Number.isFinite(value)) return DASH;
  if (Math.abs(value) >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}m`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${(value / 1_000).toFixed(1)}k`;
  }
  return numberFormatter.format(value);
};

const formatCount = (value: number): string =>
  Number.isFinite(value) ? numberFormatter.format(Math.max(0, Math.round(value))) : "0";

const formatPercent = (value: number): string =>
  Number.isFinite(value) ? `${value.toFixed(1)}%` : DASH;

const formatPerDay = (total: number, days: number): string => {
  if (!Number.isFinite(total) || !Number.isFinite(days) || days <= 0) return DASH;
  return `${(total / days).toFixed(1)}/day`;
};

const ACTIVE_ASSIGNMENT_STATUSES = new Set(["queued", "dispatching", "running", "blocked"]);

const buildDashboardAssignmentSummaries = (
  runtimeMetrics: RuntimeMetricsSnapshot | null,
): DashboardAssignmentSummary[] => {
  if (!runtimeMetrics) return [];
  const grouped = new Map<string, DashboardAssignmentSummary>();

  for (const run of runtimeMetrics.recent_runs) {
    if (!ACTIVE_ASSIGNMENT_STATUSES.has(run.status)) continue;
    const existing = grouped.get(run.silo_slug);
    if (existing) {
      existing.activeCount += 1;
      if (run.status === "blocked") existing.blockedCount += 1;
      continue;
    }
    grouped.set(run.silo_slug, {
      siloSlug: run.silo_slug,
      siloName: run.silo_name,
      activeCount: 1,
      blockedCount: run.status === "blocked" ? 1 : 0,
      latestTaskTitle: run.task_title,
      latestBoardName: run.board_name,
    });
  }

  return [...grouped.values()]
    .sort((left, right) => right.blockedCount - left.blockedCount || right.activeCount - left.activeCount)
    .slice(0, 3);
};

const toSessionSummaries = (
  sessions: unknown[] | null | undefined,
  mainSession: unknown,
): SessionSummary[] => {
  const sessionRecords = (sessions ?? []).map(toRecord).filter(Boolean) as Array<
    Record<string, unknown>
  >;
  const mainRecord = toRecord(mainSession);
  const mainIdentifiers = sessionIdentifiers(mainRecord);

  if (mainRecord && mainIdentifiers.length > 0) {
    const exists = sessionRecords.some(
      (entry) => sharesSessionIdentity(sessionIdentifiers(entry), mainIdentifiers),
    );
    if (!exists) sessionRecords.unshift(mainRecord);
  }

  const uniqueRecords: Record<string, unknown>[] = [];
  const seenIdentifiers = new Set<string>();

  for (const entry of sessionRecords) {
    const identifiers = sessionIdentifiers(entry);
    if (identifiers.length > 0 && identifiers.some((value) => seenIdentifiers.has(value))) {
      continue;
    }
    uniqueRecords.push(entry);
    identifiers.forEach((value) => seenIdentifiers.add(value));
  }

  return uniqueRecords.map((entry, index) => {
    const usageRecord = toRecord(entry.usage);
    const statsRecord = toRecord(entry.stats);
    const metricsRecord = toRecord(entry.metrics);
    const originRecord = toRecord(entry.origin);
    const candidateRecords = [entry, usageRecord, statsRecord, metricsRecord];

    const identifiers = sessionIdentifiers(entry);
    const key =
      readString(entry, ["key", "session_key", "sessionKey", "id", "sessionId"]) ??
      `session-${index}`;
    const label = readString(entry, ["label", "name", "title"]) ?? key;
    const channel = readStringFromRecords([entry, originRecord], [
      "channel",
      "source",
      "kind",
      "chatType",
    ]);
    const model = readString(entry, ["model", "model_name", "provider", "engine"]);
    const modelProvider = readString(entry, ["modelProvider", "model_provider", "provider"]);
    const lastSeenAt = readTimestampFromRecords(candidateRecords, [
      "updated_at",
      "updatedAt",
      "last_updated_at",
      "lastUpdatedAt",
      "last_seen_at",
      "lastSeen",
      "last_seen",
      "last_active_at",
      "lastActiveAt",
      "lastActivityAt",
      "activityAt",
      "created_at",
      "createdAt",
    ]);

    const usedTokens = readNumberFromRecords(candidateRecords, [
      "used",
      "used_tokens",
      "tokens",
      "current",
      "token_count",
      "tokenCount",
      "totalTokens",
      "total_tokens",
      "inputTokens",
      "input_tokens",
    ]);
    const maxTokens = readNumberFromRecords(candidateRecords, [
      "max",
      "limit",
      "token_limit",
      "capacity",
      "max_tokens",
      "maxTokens",
      "context_window",
      "contextWindow",
      "contextTokens",
      "context_tokens",
      "maxContextTokens",
      "max_context_tokens",
    ]);

    const pctFromPayload = readNumberFromRecords(candidateRecords, [
      "pct",
      "percent",
      "ratio_pct",
      "ratioPct",
      "token_pct",
      "usage_pct",
      "percentUsed",
      "contextPercent",
    ]);
    const usagePct = Number.isFinite(pctFromPayload ?? NaN)
      ? Math.max(0, Math.min(100, Math.round(pctFromPayload ?? 0)))
      : usedTokens !== null && maxTokens !== null && maxTokens > 0
        ? Math.max(0, Math.min(100, Math.round((usedTokens / maxTokens) * 100)))
        : 0;

    const usage =
      usedTokens !== null && maxTokens !== null
        ? `${compactNumber(usedTokens)}/${compactNumber(maxTokens)} (${usagePct}%)`
        : usedTokens !== null
          ? `${compactNumber(usedTokens)} tokens`
          : DASH;

    const subtitleBits = [channel, model].filter(Boolean) as string[];
    const subtitle = subtitleBits.length > 0 ? subtitleBits.join(" · ") : "Session";
    const modelWithProvider =
      modelProvider && model && modelProvider !== model ? `${model} · ${modelProvider}` : model;
    const subtitleWithProvider = [channel, modelWithProvider].filter(Boolean).join(" · ");

    return {
      key,
      title: label,
      subtitle: subtitleWithProvider || subtitle,
      usage,
      lastSeenAt,
      isMain:
        mainIdentifiers.length > 0 &&
        sharesSessionIdentity(identifiers, mainIdentifiers),
    };
  });
};

function TopMetricCard({
  title,
  value,
  secondary,
  infoText,
  icon,
  accent,
  onClick,
  ariaLabel,
}: {
  title: string;
  value: string;
  secondary?: string;
  infoText?: string;
  icon: React.ReactNode;
  accent: "blue" | "green" | "violet" | "emerald";
  onClick?: () => void;
  ariaLabel?: string;
}) {
  const iconTone =
    accent === "blue"
      ? "bg-blue-50 text-blue-600"
      : accent === "green"
        ? "bg-emerald-50 text-emerald-600"
        : accent === "violet"
          ? "bg-violet-50 text-violet-600"
          : "bg-green-50 text-green-600";

  const interactiveProps = onClick
    ? {
        role: "link" as const,
        tabIndex: 0,
        "aria-label": ariaLabel ?? title,
        onClick,
        onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          onClick();
        },
      }
    : {};

  return (
    <section
      {...interactiveProps}
      className={`rounded-xl border border-slate-200 bg-white p-4 md:p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${
        onClick
          ? "cursor-pointer focus-visible:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
          : ""
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-1.5">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              {title}
            </p>
            {infoText ? (
              <span
                className="inline-flex text-slate-400"
                title={infoText}
                aria-label={infoText}
              >
                <Info className="h-3.5 w-3.5" />
              </span>
            ) : null}
          </div>
          <div className="mt-2 flex items-end gap-2">
            <p className="font-heading text-4xl font-bold text-slate-900">{value}</p>
            {secondary ? (
              <p className="pb-1 text-xs text-slate-500">{secondary}</p>
            ) : null}
          </div>
        </div>
        <div className={`rounded-lg p-2 ${iconTone}`}>
          {icon}
        </div>
      </div>
    </section>
  );
}

function InfoBlock({
  title,
  badge,
  infoText,
  rows,
  actionHref,
  actionLabel,
  secondaryActionHref,
  secondaryActionLabel,
}: {
  title: string;
  badge?: { text: string; tone: "online" | "offline" | "neutral" };
  infoText?: string;
  rows: SummaryRow[];
  actionHref?: string;
  actionLabel?: string;
  secondaryActionHref?: string;
  secondaryActionLabel?: string;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 md:p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-1.5">
          <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
          {infoText ? (
            <span
              className="inline-flex text-slate-400"
              title={infoText}
              aria-label={infoText}
            >
              <Info className="h-3.5 w-3.5" />
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {actionHref && actionLabel ? (
            <Link
              href={actionHref}
              className="inline-flex items-center gap-1 text-xs text-slate-500 transition hover:text-slate-700"
            >
              {actionLabel}
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          ) : null}
          {secondaryActionHref && secondaryActionLabel ? (
            <Link
              href={secondaryActionHref}
              className="inline-flex items-center gap-1 text-xs text-slate-500 transition hover:text-slate-700"
            >
              {secondaryActionLabel}
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          ) : null}
          {badge ? (
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
                badge.tone === "online"
                  ? "bg-emerald-100 text-emerald-700"
                  : badge.tone === "offline"
                    ? "bg-rose-100 text-rose-700"
                    : "bg-slate-200 text-slate-700"
              }`}
            >
              {badge.text}
            </span>
          ) : null}
        </div>
      </div>
      <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
        {rows.map((row) => (
          <div key={`${row.label}-${row.value}`} className="flex items-start justify-between gap-3 px-3 py-2">
            <span className="min-w-0 text-sm text-slate-500">{row.label}</span>
            <span
              className={`max-w-[65%] break-words text-right text-sm font-medium leading-5 ${
                row.tone === "success"
                  ? "text-emerald-700"
                  : row.tone === "warning"
                    ? "text-amber-700"
                    : row.tone === "danger"
                      ? "text-rose-700"
                      : "text-slate-800"
              }`}
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { isSignedIn } = useAuth();
  const [streamedActivityEvents, setStreamedActivityEvents] = useState<StreamedActivityEvent[]>([]);
  const [retryingRunId, setRetryingRunId] = useState<string | null>(null);
  const [cancellingRunId, setCancellingRunId] = useState<string | null>(null);
  const [acknowledgingRunId, setAcknowledgingRunId] = useState<string | null>(null);
  const [escalatingRunId, setEscalatingRunId] = useState<string | null>(null);
  const streamedActivityEventsRef = useRef<StreamedActivityEvent[]>([]);
  const activityCategory = useMemo<ActivityCategory | "runtime">(() => {
    const value = searchParams.get("activity");
    if (
      value === "runtime" ||
      DASHBOARD_ACTIVITY_FILTERS.some((item) => item.value === value)
    ) {
      return value as ActivityCategory | "runtime";
    }
    return "all";
  }, [searchParams]);

  const boardsQuery = useListBoardsApiV1BoardsGet<listBoardsApiV1BoardsGetResponse, ApiError>(
    { limit: 200 },
    {
      query: {
        enabled: Boolean(isSignedIn),
        refetchInterval: 30_000,
        refetchOnMount: "always",
      },
    },
  );

  const agentsQuery = useListAgentsApiV1AgentsGet<listAgentsApiV1AgentsGetResponse, ApiError>(
    { limit: 200 },
    {
      query: {
        enabled: Boolean(isSignedIn),
        refetchInterval: 15_000,
        refetchOnMount: "always",
      },
    },
  );

  const metricsQuery = useDashboardMetricsApiV1MetricsDashboardGet<
    dashboardMetricsApiV1MetricsDashboardGetResponse,
    ApiError
  >(
    {
      range_key: DASHBOARD_RANGE,
    },
    {
      query: {
        enabled: Boolean(isSignedIn),
        refetchInterval: 15_000,
        refetchOnMount: "always",
        retry: 3,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 5000),
      },
    },
  );
  const runtimeMetricsQuery = useQuery<RuntimeMetricsSnapshot, ApiError>({
    queryKey: ["dashboard", "execution-runtime", DASHBOARD_RANGE],
    enabled: Boolean(isSignedIn),
    refetchInterval: 15_000,
    refetchOnMount: "always",
    queryFn: async () => {
      const response = await customFetch<RuntimeMetricsResponse>(
        `/api/v1/metrics/execution-runtime?range_key=${encodeURIComponent(DASHBOARD_RANGE)}`,
        { method: "GET" },
      );
      return response.data;
    },
  });
  const telemetryOpsQuery = useQuery<TelemetryOpsSnapshot, ApiError>({
    queryKey: ["dashboard", "telemetry-ops", DASHBOARD_RANGE],
    enabled: Boolean(isSignedIn),
    refetchInterval: 15_000,
    refetchOnMount: "always",
    queryFn: async () => {
      const response = await customFetch<TelemetryOpsResponse>(
        `/api/v1/metrics/telemetry-ops?range_key=${encodeURIComponent(DASHBOARD_RANGE)}`,
        { method: "GET" },
      );
      return response.data;
    },
  });
  const siloRequestsQuery = useQuery({
    queryKey: ["silo-spawn-requests", "dashboard"],
    queryFn: fetchSiloSpawnRequests,
    enabled: Boolean(isSignedIn),
    refetchInterval: 30_000,
    refetchOnMount: "always",
  });
  const silosQuery = useQuery({
    queryKey: ["silos", "dashboard"],
    queryFn: fetchSilos,
    enabled: Boolean(isSignedIn),
    refetchInterval: 30_000,
    refetchOnMount: "always",
  });

  const invalidateRuntimeViews = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["dashboard", "execution-runtime", DASHBOARD_RANGE] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard", "telemetry-ops", DASHBOARD_RANGE] }),
      queryClient.invalidateQueries({ queryKey: ["/api/v1/metrics/dashboard", { range_key: DASHBOARD_RANGE }] }),
      queryClient.invalidateQueries({ queryKey: ["/api/v1/activity", { limit: 200 }] }),
    ]);
  };

  const retryRuntimeRun = async (run: DashboardRuntimeRunSnapshot): Promise<void> => {
    setRetryingRunId(run.run_id);
    try {
      await customFetch<{ data: unknown; status: number; headers: Headers }>(
        `/api/v1/boards/${encodeURIComponent(run.board_id)}/tasks/${encodeURIComponent(run.task_id)}/execution-runs/${encodeURIComponent(run.run_id)}/retry-dispatch`,
        { method: "POST" },
      );
      await invalidateRuntimeViews();
    } finally {
      setRetryingRunId(null);
    }
  };

  const cancelRuntimeRun = async (run: DashboardRuntimeRunSnapshot): Promise<void> => {
    setCancellingRunId(run.run_id);
    try {
      await customFetch<{ data: unknown; status: number; headers: Headers }>(
        `/api/v1/boards/${encodeURIComponent(run.board_id)}/tasks/${encodeURIComponent(run.task_id)}/execution-runs/${encodeURIComponent(run.run_id)}/cancel`,
        { method: "POST" },
      );
      await invalidateRuntimeViews();
    } finally {
      setCancellingRunId(null);
    }
  };

  const acknowledgeRuntimeRun = async (run: DashboardRuntimeRunSnapshot): Promise<void> => {
    setAcknowledgingRunId(run.run_id);
    try {
      await customFetch<{ data: unknown; status: number; headers: Headers }>(
        `/api/v1/boards/${encodeURIComponent(run.board_id)}/tasks/${encodeURIComponent(run.task_id)}/execution-runs/${encodeURIComponent(run.run_id)}/acknowledge`,
        { method: "POST" },
      );
      await invalidateRuntimeViews();
    } finally {
      setAcknowledgingRunId(null);
    }
  };

  const escalateRuntimeRun = async (run: DashboardRuntimeRunSnapshot): Promise<void> => {
    setEscalatingRunId(run.run_id);
    try {
      await customFetch<{ data: unknown; status: number; headers: Headers }>(
        `/api/v1/boards/${encodeURIComponent(run.board_id)}/tasks/${encodeURIComponent(run.task_id)}/execution-runs/${encodeURIComponent(run.run_id)}/escalate`,
        { method: "POST" },
      );
      await invalidateRuntimeViews();
    } finally {
      setEscalatingRunId(null);
    }
  };

  const activityQuery = useListActivityApiV1ActivityGet<listActivityApiV1ActivityGetResponse, ApiError>(
    { limit: 200 },
    {
      query: {
        enabled: Boolean(isSignedIn),
        refetchInterval: 15_000,
        refetchOnMount: "always",
      },
    },
  );

  const boards = useMemo(
    () =>
      boardsQuery.data?.status === 200
        ? [...(boardsQuery.data.data.items ?? [])].sort((a, b) => a.name.localeCompare(b.name))
        : [],
    [boardsQuery.data],
  );

  const agents = useMemo(
    () =>
      agentsQuery.data?.status === 200
        ? [...(agentsQuery.data.data.items ?? [])].sort((a, b) => a.name.localeCompare(b.name))
        : [],
    [agentsQuery.data],
  );

  const metrics = metricsQuery.data?.status === 200 ? metricsQuery.data.data : null;
  const runtimeMetrics = runtimeMetricsQuery.data ?? null;
  const telemetryOpsMetrics = telemetryOpsQuery.data ?? null;
  const assignmentSummaries = useMemo(
    () => buildDashboardAssignmentSummaries(runtimeMetrics),
    [runtimeMetrics],
  );
  const siloRequestsSummary = useMemo<SiloRequestsSummary>(() => {
    const now = Date.now();
    const requests = siloRequestsQuery.data ?? [];
    return requests.reduce<SiloRequestsSummary>(
      (acc, request) => {
        if (isOpenSiloRequestStatus(request.status)) {
          acc.openCount += 1;
          if (request.priority === "urgent") acc.urgentCount += 1;
          if (request.priority === "high") acc.highCount += 1;
          if (request.source_task_title) acc.demandLinkedCount += 1;
          if (describeSiloRequestPressure(request) === "Active workload pressure") {
            acc.activeWorkloadCount += 1;
          }
        }
        if (request.materialized_at) {
          const materializedAt = new Date(request.materialized_at).getTime();
          if (
            Number.isFinite(materializedAt) &&
            now - materializedAt <= 7 * 24 * 60 * 60 * 1000
          ) {
            acc.materializedRecentCount += 1;
          }
        }
        return acc;
      },
      {
        openCount: 0,
        urgentCount: 0,
        highCount: 0,
        materializedRecentCount: 0,
        demandLinkedCount: 0,
        activeWorkloadCount: 0,
      },
    );
  }, [siloRequestsQuery.data]);
  const siloHealthViewModel = useMemo(
    () => buildDashboardSiloHealthViewModel(silosQuery.data ?? []),
    [silosQuery.data],
  );
  const siloHealthContextHref = useMemo(() => {
    return siloHealthViewModel.primarySiloSlug
      ? `/silos/${siloHealthViewModel.primarySiloSlug}`
      : null;
  }, [siloHealthViewModel.primarySiloSlug]);

  const onlineAgents = useMemo(
    () => agents.filter((agent) => (agent.status ?? "").toLowerCase() === "online").length,
    [agents],
  );
  const gatewayTargets = useMemo<GatewayTarget[]>(() => {
    const byGateway = new Map<string, GatewayTarget>();
    for (const board of boards) {
      const gatewayId = board.gateway_id;
      if (!gatewayId) continue;
      if (byGateway.has(gatewayId)) continue;
      byGateway.set(gatewayId, {
        gatewayId,
        boardId: board.id,
        boardName: board.name,
      });
    }
    return [...byGateway.values()].sort((a, b) => a.boardName.localeCompare(b.boardName));
  }, [boards]);
  const hasConfiguredGateways = gatewayTargets.length > 0;

  const gatewayStatusesQuery = useQuery<GatewaySnapshot[], ApiError>({
    queryKey: [
      "dashboard",
      "gateway-statuses",
      gatewayTargets.map((target) => `${target.gatewayId}:${target.boardId}`),
    ],
    enabled: Boolean(isSignedIn && hasConfiguredGateways),
    refetchInterval: 15_000,
    refetchOnMount: "always",
    queryFn: async ({ signal }) => {
      return Promise.all(
        gatewayTargets.map(async (target): Promise<GatewaySnapshot> => {
          try {
            const response = await gatewaysStatusApiV1GatewaysStatusGet(
              { board_id: target.boardId },
              { signal },
            );
            if (response.status !== 200) {
              return {
                ...target,
                connected: false,
                gatewayUrl: null,
                sessionsCount: 0,
                sessions: [],
                mainSession: null,
                mainSessionError: null,
                error: null,
                requestError: `Gateway status request failed (${response.status})`,
              };
            }
            const payload: GatewaysStatusResponse = response.data;
            return {
              ...target,
              connected: Boolean(payload.connected),
              gatewayUrl: payload.gateway_url ?? null,
              sessionsCount: Number(payload.sessions_count ?? 0),
              sessions: Array.isArray(payload.sessions) ? payload.sessions : [],
              mainSession: payload.main_session ?? null,
              mainSessionError: payload.main_session_error ?? null,
              error: payload.error ?? null,
              requestError: null,
            };
          } catch (error) {
            if (signal.aborted) throw error;
            return {
              ...target,
              connected: false,
              gatewayUrl: null,
              sessionsCount: 0,
              sessions: [],
              mainSession: null,
              mainSessionError: null,
              error: null,
              requestError:
                error instanceof Error ? error.message : "Gateway status request failed.",
            };
          }
        }),
      );
    },
  });

  const gatewaySnapshots = useMemo(
    () => gatewayStatusesQuery.data ?? [],
    [gatewayStatusesQuery.data],
  );
  const sessionSummaries = useMemo(
    () =>
      gatewaySnapshots.flatMap((snapshot) => {
        if (snapshot.requestError) return [];
        const sourceLabel = snapshot.gatewayUrl || snapshot.boardName;
        return toSessionSummaries(snapshot.sessions, snapshot.mainSession).map((session) => ({
          ...session,
          key: `${snapshot.gatewayId}:${session.key}`,
          subtitle: `${sourceLabel} · ${session.subtitle}`,
        }));
      }),
    [gatewaySnapshots],
  );

  const activityEvents = useMemo(
    () => {
      const seeded =
        activityQuery.data?.status === 200
          ? [...(activityQuery.data.data.items ?? [])]
          : [];
      const merged = new Map<string, ActivityEventRead>();
      [...seeded, ...streamedActivityEvents].forEach((event) => {
        merged.set(event.id, event);
      });
      return [...merged.values()];
    },
    [activityQuery.data, streamedActivityEvents],
  );

  useEffect(() => {
    streamedActivityEventsRef.current = streamedActivityEvents;
  }, [streamedActivityEvents]);

  const orderedActivityEvents = useMemo(
    () =>
      [...activityEvents].sort((a, b) => {
        const left = parseTimestamp(a.created_at)?.getTime() ?? 0;
        const right = parseTimestamp(b.created_at)?.getTime() ?? 0;
        return right - left;
      }),
    [activityEvents],
  );

  const recentLogs = useMemo(() => {
    const filtered =
      activityCategory === "all"
        ? orderedActivityEvents
        : orderedActivityEvents.filter((event) => {
            const category = activityCategoryForEvent(event.event_type);
            if (activityCategory === "runtime") {
              return category === "runs" || category === "runtime";
            }
            return category === activityCategory;
          });
    return filtered.slice(0, 8);
  }, [activityCategory, orderedActivityEvents]);

  const workerTelemetrySummary = useMemo(
    () => buildWorkerTelemetrySummary(orderedActivityEvents, telemetryOpsMetrics),
    [orderedActivityEvents, telemetryOpsMetrics],
  );

  const webhookTelemetrySummary = useMemo(
    () => buildWebhookTelemetrySummary(orderedActivityEvents, telemetryOpsMetrics),
    [orderedActivityEvents, telemetryOpsMetrics],
  );

  const updateActivityCategory = (next: ActivityCategory | "runtime") => {
    const params = new URLSearchParams(searchParams.toString());
    if (next === "all") {
      params.delete("activity");
    } else {
      params.set("activity", next);
    }
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  };

  useEffect(() => {
    if (!isSignedIn) return;

    let isCancelled = false;
    const abortController = new AbortController();
    const connect = async () => {
      try {
        const params = new URLSearchParams();
        const since = latestActivityTimestamp(streamedActivityEventsRef.current);
        if (since) {
          params.set("since", since);
        }
        const streamResult = await customFetch<{
          data: Response;
          status: number;
          headers: Headers;
        }>(`/api/v1/activity/stream${params.toString() ? `?${params.toString()}` : ""}`, {
          method: "GET",
          headers: { Accept: "text/event-stream" },
          signal: abortController.signal,
        });
        if (streamResult.status !== 200) {
          throw new Error("Unable to connect activity stream.");
        }
        const response = streamResult.data as Response;
        if (!(response instanceof Response) || !response.body) {
          throw new Error("Unable to connect activity stream.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (!isCancelled) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          buffer = buffer.replace(/\r\n/g, "\n");
          let boundary = buffer.indexOf("\n\n");
          while (boundary !== -1) {
            const raw = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            const lines = raw.split("\n");
            let eventType = "message";
            let data = "";
            for (const line of lines) {
              if (line.startsWith("event:")) {
                eventType = line.slice(6).trim();
              } else if (line.startsWith("data:")) {
                data += line.slice(5).trim();
              }
            }
            if (eventType === "activity" && data) {
              try {
                const payload = JSON.parse(data) as { activity?: ActivityEventRead };
                if (payload.activity) {
                  setStreamedActivityEvents((prev) => {
                    if (prev.some((item) => item.id === payload.activity?.id)) return prev;
                    return [payload.activity!, ...prev].slice(0, 200);
                  });
                }
              } catch {
                continue;
              }
            }
            boundary = buffer.indexOf("\n\n");
          }
        }
      } catch {
        return;
      }
    };

    void connect();
    return () => {
      isCancelled = true;
      abortController.abort();
    };
  }, [isSignedIn]);

  const latestThroughputPoint =
    metrics?.throughput.primary.points?.[metrics.throughput.primary.points.length - 1] ?? null;
  const throughputTotal = (metrics?.throughput.primary.points ?? []).reduce(
    (sum, point) => sum + Number(point.value ?? 0),
    0,
  );
  const completionDaysCount = (metrics?.throughput.primary.points ?? []).reduce(
    (sum, point) => sum + (Number(point.value ?? 0) > 0 ? 1 : 0),
    0,
  );

  const inboxTasksMetric = metrics?.kpis.inbox_tasks ?? 0;
  const inProgressTasksMetric = metrics?.kpis.in_progress_tasks ?? 0;
  const reviewTasksMetric = metrics?.kpis.review_tasks ?? 0;
  const doneTasksMetric = metrics?.kpis.done_tasks ?? 0;

  const activeAgentsMetric = onlineAgents;
  const tasksTotal = inboxTasksMetric + inProgressTasksMetric + reviewTasksMetric + doneTasksMetric;
  const tasksInProgressMetric = metrics?.kpis.tasks_in_progress ?? inProgressTasksMetric;
  const errorRateMetric = Number(metrics?.kpis.error_rate_pct ?? 0);
  const reviewBacklogRatio =
    inProgressTasksMetric > 0 ? reviewTasksMetric / inProgressTasksMetric : null;

  const gatewayConnectedCount = gatewaySnapshots.filter(
    (snapshot) => !snapshot.requestError && snapshot.connected,
  ).length;
  const gatewayDisconnectedCount = gatewaySnapshots.filter(
    (snapshot) => !snapshot.requestError && !snapshot.connected,
  ).length;
  const gatewayUnavailableCount = gatewaySnapshots.filter(
    (snapshot) => Boolean(snapshot.requestError),
  ).length;
  const gatewayHealthErrorCount = gatewaySnapshots.filter(
    (snapshot) => Boolean(snapshot.error || snapshot.mainSessionError),
  ).length;

  const countedSessions = gatewaySnapshots.reduce(
    (sum, snapshot) => sum + Math.max(0, snapshot.sessionsCount),
    0,
  );
  const activeSessions = Math.max(countedSessions, sessionSummaries.length);

  const gatewayStatusLabel = !hasConfiguredGateways
    ? "Not configured"
    : gatewayStatusesQuery.isLoading
      ? "Checking"
      : gatewayConnectedCount === gatewayTargets.length
        ? "All connected"
        : gatewayConnectedCount > 0
          ? "Partially connected"
          : gatewayUnavailableCount === gatewayTargets.length
            ? "Unavailable"
            : "Disconnected";
  const gatewayBadgeTone: "online" | "offline" | "neutral" =
    gatewayStatusLabel === "All connected"
      ? "online"
      : gatewayStatusLabel === "Partially connected" ||
          gatewayStatusLabel === "Disconnected" ||
          gatewayStatusLabel === "Unavailable"
        ? "offline"
        : "neutral";
  const gatewayStatusTone: SummaryRow["tone"] =
    gatewayStatusLabel === "All connected"
      ? "success"
      : gatewayStatusLabel === "Checking" || gatewayStatusLabel === "Not configured"
        ? "default"
        : gatewayStatusLabel === "Partially connected" || gatewayStatusLabel === "Disconnected"
          ? "warning"
          : "danger";

  const workloadRows: SummaryRow[] = [
    {
      label: "Total work items",
      value: formatCount(tasksTotal),
    },
    {
      label: "Inbox",
      value: formatCount(inboxTasksMetric),
    },
    {
      label: "In progress",
      value: formatCount(inProgressTasksMetric),
      tone: inProgressTasksMetric > 0 ? "warning" : "default",
    },
    {
      label: "In review",
      value: formatCount(reviewTasksMetric),
    },
    {
      label: "Completed",
      value: formatCount(doneTasksMetric),
      tone: doneTasksMetric > 0 ? "success" : "default",
    },
  ];

  const throughputRows: SummaryRow[] = [
    {
      label: "Completed tasks",
      value: formatCount(throughputTotal),
    },
    { label: "Average throughput", value: formatPerDay(throughputTotal, DASHBOARD_RANGE_DAYS) },
    {
      label: "Error rate",
      value: formatPercent(errorRateMetric),
      tone: errorRateMetric > 0 ? "warning" : "success",
    },
    {
      label: "Completion consistency",
      value: `${formatCount(completionDaysCount)} active days`,
      tone: completionDaysCount >= Math.ceil(DASHBOARD_RANGE_DAYS * 0.75) ? "success" : "default",
    },
    {
      label: "Review backlog ratio",
      value:
        reviewBacklogRatio !== null
          ? `${reviewBacklogRatio.toFixed(2)}x`
          : reviewTasksMetric > 0
            ? "∞"
            : "0.00x",
      tone:
        reviewBacklogRatio !== null
          ? reviewBacklogRatio > 1
            ? "warning"
            : "success"
          : reviewTasksMetric > 0
            ? "warning"
            : "success",
    },
  ];

  const gatewayRows: SummaryRow[] = [
    { label: "Gateway status", value: gatewayStatusLabel, tone: gatewayStatusTone },
    { label: "Configured gateways", value: formatCount(gatewayTargets.length) },
    {
      label: "Connected gateways",
      value: formatCount(gatewayConnectedCount),
      tone: gatewayConnectedCount > 0 ? "success" : "default",
    },
    {
      label: "Unavailable gateways",
      value: formatCount(gatewayUnavailableCount),
      tone: gatewayUnavailableCount > 0 ? "danger" : "default",
    },
    {
      label: "Gateways with issues",
      value: formatCount(gatewayHealthErrorCount + gatewayDisconnectedCount),
      tone: gatewayHealthErrorCount + gatewayDisconnectedCount > 0 ? "warning" : "success",
    },
  ];
  const pendingApprovalItems = metrics?.pending_approvals.items ?? [];
  const pendingApprovalsTotal = metrics?.pending_approvals.total ?? 0;
  const hasPendingApprovals = pendingApprovalItems.length > 0;
  const activityFeedHref = useMemo(() => {
    if (activityCategory === "all") return "/activity";
    const params = new URLSearchParams();
    if (activityCategory === "runtime") {
      params.set("category", "runs");
    } else {
      params.set("category", activityCategory);
    }
    return `/activity?${params.toString()}`;
  }, [activityCategory]);
  const workerFeedHref = useMemo(() => "/activity?category=runtime", []);
  const webhookFeedHref = useMemo(() => "/activity?category=gateway", []);
  const workerContextHref = useMemo(() => {
    const boardId = telemetryOpsMetrics?.worker.latest_board_id;
    const taskId = telemetryOpsMetrics?.worker.latest_task_id;
    if (!boardId) return null;
    if (taskId) {
      return `/boards/${encodeURIComponent(boardId)}?taskId=${encodeURIComponent(taskId)}`;
    }
    return `/boards/${encodeURIComponent(boardId)}`;
  }, [telemetryOpsMetrics]);
  const webhookContextHref = useMemo(() => {
    const boardId = telemetryOpsMetrics?.webhook.latest_board_id;
    if (!boardId) return null;
    return `/boards/${encodeURIComponent(boardId)}`;
  }, [telemetryOpsMetrics]);

  const shouldIgnoreRowNavigation = (target: EventTarget | null): boolean => {
    if (!(target instanceof HTMLElement)) return false;
    return Boolean(target.closest("a"));
  };

  const buildActivityEventHref = (event: ActivityEventRead): string => {
    const routeName = event.route_name ?? null;
    const routeParams = event.route_params ?? {};

    if (routeName === "board.approvals") {
      const boardId = routeParams.boardId;
      if (boardId) {
        return `/boards/${encodeURIComponent(boardId)}/approvals`;
      }
    }

    if (routeName === "board") {
      const boardId = routeParams.boardId;
      if (boardId) {
        const params = new URLSearchParams();
        Object.entries(routeParams).forEach(([key, value]) => {
          if (key !== "boardId") params.set(key, value);
        });
        const query = params.toString();
        return query
          ? `/boards/${encodeURIComponent(boardId)}?${query}`
          : `/boards/${encodeURIComponent(boardId)}`;
      }
    }

    const params = new URLSearchParams(
      Object.keys(routeParams).length > 0
        ? routeParams
        : {
            eventId: event.id,
            eventType: event.event_type,
            createdAt: event.created_at,
          },
    );
    if (event.task_id && !params.has("taskId")) {
      params.set("taskId", event.task_id);
    }
    return `${activityFeedHref}?${params.toString()}`;
  };

  const navigateToActivityFeed = (href: string) => {
    router.push(href);
  };

  const buildRuntimeRunHref = (run: DashboardRuntimeRunSnapshot): string => {
    const params = new URLSearchParams({ taskId: run.task_id });
    return `/boards/${encodeURIComponent(run.board_id)}?${params.toString()}`;
  };

  const handleLogRowClick = (
    event: MouseEvent<HTMLDivElement>,
    href: string,
  ) => {
    if (shouldIgnoreRowNavigation(event.target)) return;
    navigateToActivityFeed(href);
  };

  const handleLogRowKeyDown = (
    event: KeyboardEvent<HTMLDivElement>,
    href: string,
  ) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    if (shouldIgnoreRowNavigation(event.target)) return;
    event.preventDefault();
    navigateToActivityFeed(href);
  };

  return (
    <DashboardShell>
      <SignedOut>
        <SignedOutPanel
          message="Sign in to access the dashboard."
          forceRedirectUrl="/onboarding"
          signUpForceRedirectUrl="/onboarding"
        />
      </SignedOut>
      <SignedIn>
        <DashboardSidebar />
        <main className="flex-1 overflow-y-auto bg-slate-50">
          <div className="p-4 md:p-8">
            {metricsQuery.error ? (
              <div className="mb-4 rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
                Load failed: {metricsQuery.error.message}
              </div>
            ) : null}

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <TopMetricCard
                title="Online Agents"
                value={formatCount(activeAgentsMetric)}
                secondary={`${formatCount(agents.length)} total`}
                icon={<Bot className="h-4 w-4" />}
                accent="blue"
              />
              <TopMetricCard
                title="Tasks In Progress"
                value={formatCount(tasksInProgressMetric)}
                secondary={`${formatCount(tasksTotal)} total`}
                icon={<LayoutGrid className="h-4 w-4" />}
                accent="green"
              />
              <TopMetricCard
                title="Error Rate"
                value={formatPercent(errorRateMetric)}
                secondary={`${formatCount(Number(latestThroughputPoint?.value ?? 0))} completed (latest)`}
                icon={<Activity className="h-4 w-4" />}
                accent="violet"
              />
              <TopMetricCard
                title="Completion Speed"
                value={formatPerDay(throughputTotal, DASHBOARD_RANGE_DAYS)}
                secondary={`${formatCount(throughputTotal)} completed`}
                infoText={`Based on ${DASHBOARD_RANGE_LABEL}`}
                icon={<Timer className="h-4 w-4" />}
                accent="emerald"
              />
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
              <InfoBlock
                title="Workload"
                rows={workloadRows}
              />
              <InfoBlock
                title="Throughput"
                infoText={`All throughput values are calculated for ${DASHBOARD_RANGE_LABEL}`}
                rows={throughputRows}
              />
              <InfoBlock
                title="Gateway Health"
                badge={{
                  text: gatewayStatusLabel,
                  tone: gatewayBadgeTone,
                }}
                rows={gatewayRows}
              />
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-4">
              <InfoBlock
                title="Silo Health"
                infoText="Core operating posture for the silos that can take work now."
                badge={siloHealthViewModel.badge}
                rows={[
                  { label: "Healthy", value: formatCount(siloHealthViewModel.summary.healthyCount) },
                  { label: "Busy", value: formatCount(siloHealthViewModel.summary.busyCount) },
                  { label: "Blocked", value: formatCount(siloHealthViewModel.summary.blockedCount) },
                  {
                    label: "Degraded",
                    value: formatCount(siloHealthViewModel.summary.degradedCount),
                  },
                  { label: "Needs setup", value: formatCount(siloHealthViewModel.summary.needsSetupCount) },
                ]}
                actionHref="/silos"
                actionLabel="Open silos"
                secondaryActionHref={siloHealthContextHref ?? undefined}
                secondaryActionLabel={siloHealthContextHref ? "Open next silo" : undefined}
              />
              <InfoBlock
                title="Worker Telemetry"
                infoText="Summarized from recent queue worker activity events."
                badge={workerTelemetrySummary.badge}
                rows={workerTelemetrySummary.rows}
                actionHref={workerFeedHref}
                actionLabel="Open feed"
                secondaryActionHref={workerContextHref ?? undefined}
                secondaryActionLabel={workerContextHref ? "Open task" : undefined}
              />
              <InfoBlock
                title="Webhook Telemetry"
                infoText="Summarized from recent webhook delivery activity events."
                badge={webhookTelemetrySummary.badge}
                rows={webhookTelemetrySummary.rows}
                actionHref={webhookFeedHref}
                actionLabel="Open feed"
                secondaryActionHref={webhookContextHref ?? undefined}
                secondaryActionLabel={webhookContextHref ? "Open board" : undefined}
              />
              <InfoBlock
                title="Silo Requests"
                infoText="Secondary planning queue for future silo demand."
                rows={[
                  { label: "Open", value: formatCount(siloRequestsSummary.openCount) },
                  { label: "Urgent", value: formatCount(siloRequestsSummary.urgentCount) },
                  {
                    label: "Demand-linked",
                    value: formatCount(siloRequestsSummary.demandLinkedCount),
                  },
                  {
                    label: "Materialized",
                    value: formatCount(siloRequestsSummary.materializedRecentCount),
                  },
                ]}
                actionHref="/silos/requests"
                actionLabel="Open queue"
              />
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
              <TopMetricCard
                title="Worker Failures"
                value={formatCount(
                  telemetryOpsMetrics
                    ? telemetryOpsMetrics.worker.failure_count_7d +
                        telemetryOpsMetrics.worker.dequeue_failure_count_7d
                    : 0,
                )}
                secondary={
                  telemetryOpsMetrics?.worker.latest_at
                    ? `Latest ${formatRelativeTimestamp(telemetryOpsMetrics.worker.latest_at)}`
                    : "No recent worker signal"
                }
                infoText={`Queue worker failures and dequeue failures over ${DASHBOARD_RANGE_LABEL}`}
                icon={<Timer className="h-4 w-4" />}
                accent="violet"
                onClick={() => router.push(workerFeedHref)}
                ariaLabel="Open runtime activity feed for worker telemetry"
              />
              <TopMetricCard
                title="Webhook Failures"
                value={formatCount(telemetryOpsMetrics?.webhook.failure_count_7d ?? 0)}
                secondary={
                  telemetryOpsMetrics?.webhook.retried_count_7d
                    ? `${formatCount(telemetryOpsMetrics.webhook.retried_count_7d)} retried`
                    : "No retries"
                }
                infoText={`Webhook dispatch failures over ${DASHBOARD_RANGE_LABEL}`}
                icon={<Shield className="h-4 w-4" />}
                accent="green"
                onClick={() => router.push(webhookFeedHref)}
                ariaLabel="Open gateway activity feed for webhook telemetry"
              />
            </div>

            <section className="mt-4 rounded-xl border border-slate-200 bg-white p-4 md:p-6 shadow-sm">
              <div className="mb-3 flex items-center justify-between gap-3">
                <h3 className="text-lg font-semibold text-slate-900">Pending Approvals</h3>
                <Link
                  href="/approvals"
                  className="inline-flex items-center gap-1 text-xs text-slate-500 transition hover:text-slate-700"
                >
                  Open global approvals
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              </div>

              {!metrics && metricsQuery.isLoading ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
                  Loading pending approvals...
                </div>
              ) : !metrics && metricsQuery.error ? (
                <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
                  Pending approvals are temporarily unavailable.
                </div>
              ) : hasPendingApprovals ? (
                <div className="space-y-2">
                  <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
                    {pendingApprovalItems.map((item) => (
                      <Link
                        key={item.approval_id}
                        href={`/boards/${item.board_id}/approvals`}
                        className="flex items-center justify-between gap-3 px-3 py-2 transition hover:bg-slate-50"
                      >
                        <span className="min-w-0 text-sm text-slate-700">
                          <span className="block truncate font-medium text-slate-800">
                            {item.task_title || "Pending approval"}
                          </span>
                          <span className="block truncate text-xs text-slate-500">
                            {item.board_name} · {item.confidence}% score
                          </span>
                        </span>
                        <span className="shrink-0 text-xs text-slate-500">
                          {formatRelativeTimestamp(item.created_at)}
                        </span>
                      </Link>
                    ))}
                  </div>
                  {pendingApprovalsTotal > pendingApprovalItems.length ? (
                    <p className="text-xs text-slate-500">
                      Showing latest {formatCount(pendingApprovalItems.length)} of{" "}
                      {formatCount(pendingApprovalsTotal)} pending approvals.
                    </p>
                  ) : null}
                </div>
              ) : (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
                  No pending approvals across your boards.
                </div>
              )}
            </section>

            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
              <section className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white p-4 md:p-6 shadow-sm">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h3 className="text-lg font-semibold text-slate-900">Sessions</h3>
                  <span className="text-xs text-slate-500">{formatCount(activeSessions)}</span>
                </div>
                <div className="max-h-[310px] space-y-2 overflow-x-hidden overflow-y-auto pr-1">
                  {!hasConfiguredGateways ? (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
                      No gateways are configured for any board yet.
                    </div>
                  ) : gatewayStatusesQuery.isLoading ? (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
                      Loading sessions...
                    </div>
                  ) : sessionSummaries.length > 0 ? (
                    <>
                      {gatewayUnavailableCount > 0 ? (
                        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
                          {formatCount(gatewayUnavailableCount)} gateway
                          {gatewayUnavailableCount === 1 ? "" : "s"} unavailable; showing sessions
                          from reachable gateways.
                        </div>
                      ) : null}
                      {sessionSummaries.map((session) => (
                        <div
                          key={session.key}
                          className="overflow-hidden rounded-lg border border-slate-200 bg-white px-3 py-2"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm font-medium text-slate-900">
                                <span
                                  className={`mr-2 inline-block h-2 w-2 rounded-full ${
                                    session.isMain ? "bg-emerald-500" : "bg-slate-400"
                                  }`}
                                />
                                {session.title}
                              </p>
                              <p className="mt-0.5 truncate text-xs text-slate-500">{session.subtitle}</p>
                            </div>
                            <div className="min-w-0 max-w-[45%] text-right">
                              <p className="truncate text-xs font-medium text-slate-700">
                                {session.usage === DASH ? "Usage unavailable" : session.usage}
                              </p>
                              <p className="text-[11px] text-slate-500">
                                {session.lastSeenAt
                                  ? formatRelativeTimestamp(session.lastSeenAt)
                                  : "Activity unavailable"}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </>
                  ) : gatewayUnavailableCount === gatewayTargets.length ? (
                    <div className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
                      Session data is unavailable for all configured gateways.
                    </div>
                  ) : (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
                      No active sessions detected.
                    </div>
                  )}
                </div>
              </section>

              <section className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white p-4 md:p-6 shadow-sm">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-lg font-semibold text-slate-900">Recent Activity</h3>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {DASHBOARD_ACTIVITY_FILTERS.map((filter) => (
                        <button
                          key={filter.value}
                          type="button"
                          onClick={() => updateActivityCategory(filter.value)}
                          className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition ${
                            activityCategory === filter.value
                              ? "border-slate-900 bg-slate-900 text-white"
                              : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
                          }`}
                        >
                          {filter.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <Link
                    href={activityFeedHref}
                    className="inline-flex items-center gap-1 text-xs text-slate-500 transition hover:text-slate-700"
                  >
                    Open feed
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
                <div className="max-h-[310px] space-y-2 overflow-x-hidden overflow-y-auto pr-1">
                  {recentLogs.length > 0 ? (
                    recentLogs.map((event) => {
                      const eventHref = buildActivityEventHref(event);
                      const content = resolveActivityFeedContent(
                        event.event_type,
                        event.message,
                        event.payload,
                      );
                      return (
                        <div
                          key={event.id}
                          role="link"
                          tabIndex={0}
                        aria-label={`Open related context for ${event.event_type} activity`}
                          onClick={(interactionEvent) =>
                            handleLogRowClick(interactionEvent, eventHref)
                          }
                          onKeyDown={(interactionEvent) =>
                            handleLogRowKeyDown(interactionEvent, eventHref)
                          }
                          className="cursor-pointer overflow-hidden rounded-lg border border-slate-200 bg-white px-3 py-2 transition hover:border-slate-300 focus-visible:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1 overflow-hidden">
                              <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                                <span
                                  className={`inline-flex items-center rounded-full border px-2 py-0.5 font-medium ${dashboardActivityPillClass(
                                    event.event_type,
                                  )}`}
                                >
                                  {dashboardActivityLabel(event.event_type)}
                                </span>
                                <p className="uppercase tracking-wider text-slate-400">
                                  {event.event_type}
                                </p>
                                {content.runtimeStatus ? (
                                  <span className="inline-flex align-middle">
                                    <RuntimeRunStatusChip status={content.runtimeStatus} />
                                  </span>
                                ) : null}
                              </div>
                              <div className="break-words text-sm font-medium text-slate-900 [&_ol]:mb-0 [&_p]:mb-0 [&_pre]:my-1 [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_ul]:mb-0">
                                <Markdown
                                  content={content.summary}
                                  variant="comment"
                                />
                              </div>
                              <RuntimeRunMetaGrid details={content.details} itemKey={event.id} />
                            </div>
                            <div className="shrink-0 text-right text-[11px] text-slate-500">
                              <p>{formatRelativeTimestamp(event.created_at)}</p>
                              <p>{formatTimestamp(event.created_at)}</p>
                            </div>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="flex h-[240px] flex-col items-center justify-center rounded-lg border border-slate-200 bg-white text-sm text-slate-500">
                      <Shield className="mb-2 h-5 w-5 text-slate-400" />
                      No activity yet
                      <p className="mt-1 text-xs text-slate-500">Activity appears here when events are emitted.</p>
                    </div>
                  )}
                </div>
              </section>

              <section className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white p-4 md:p-6 shadow-sm md:col-span-2">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h3 className="text-lg font-semibold text-slate-900">Runtime Runs</h3>
                  <span className="text-xs text-slate-500">
                    {runtimeMetrics
                      ? `${compactNumber(runtimeMetrics.total_tokens_7d)} tokens / ${DASHBOARD_RANGE_LABEL}`
                      : "Loading"}
                  </span>
                </div>
                <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Active</p>
                    <p className="mt-1 text-lg font-semibold text-slate-900">
                      {formatCount(runtimeMetrics?.active_runs ?? 0)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Queued</p>
                    <p className="mt-1 text-lg font-semibold text-slate-900">
                      {formatCount(runtimeMetrics?.queued_runs ?? 0)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Succeeded</p>
                    <p className="mt-1 text-lg font-semibold text-emerald-700">
                      {formatCount(runtimeMetrics?.succeeded_runs_7d ?? 0)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Failed</p>
                    <p className="mt-1 text-lg font-semibold text-rose-700">
                      {formatCount(runtimeMetrics?.failed_runs_7d ?? 0)}
                    </p>
                  </div>
                </div>
                {assignmentSummaries.length > 0 ? (
                  <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Active assignments
                      </p>
                      <span className="text-[11px] text-slate-500">
                        Current silo ownership
                      </span>
                    </div>
                    <div className="mt-3 grid gap-3 lg:grid-cols-3">
                      {assignmentSummaries.map((assignment) => (
                        <Link
                          key={assignment.siloSlug}
                          href={`/silos/${assignment.siloSlug}`}
                          className="rounded-lg border border-slate-200 bg-white px-3 py-3 transition hover:border-slate-300"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-medium text-slate-900">
                                {assignment.siloName}
                              </p>
                              <p className="mt-1 text-xs text-slate-500">
                                {assignment.latestBoardName} · {assignment.latestTaskTitle}
                              </p>
                            </div>
                            <div className="text-right text-[11px] text-slate-500">
                              <p>Active {assignment.activeCount}</p>
                              {assignment.blockedCount > 0 ? (
                                <p className="text-rose-700">Blocked {assignment.blockedCount}</p>
                              ) : null}
                            </div>
                          </div>
                        </Link>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="max-h-[280px] space-y-2 overflow-x-hidden overflow-y-auto pr-1">
                  {runtimeMetricsQuery.isLoading ? (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
                      Loading runtime runs...
                    </div>
                  ) : runtimeMetrics && runtimeMetrics.recent_runs.length > 0 ? (
                    runtimeMetrics.recent_runs.map((run) => (
                      (() => {
                        const duration = runtimeRunTimingLabel(run);
                        const operatorState = runtimeRunOperatorState(run);
                        const guidance = runtimeRunOperatorGuidance(run);
                        const detailRows = [
                          run.issue_identifier ? { label: "Issue", value: run.issue_identifier } : null,
                          run.runner_kind ? { label: "Runner", value: run.runner_kind } : null,
                          run.completion_kind ? { label: "Completion", value: run.completion_kind } : null,
                          run.failure_reason ? { label: "Failure reason", value: run.failure_reason } : null,
                          run.block_reason ? { label: "Block reason", value: run.block_reason } : null,
                          run.cancel_reason ? { label: "Cancel reason", value: run.cancel_reason } : null,
                          run.stall_reason ? { label: "Stall reason", value: run.stall_reason } : null,
                          run.turn_count != null ? { label: "Turns", value: String(run.turn_count) } : null,
                          run.session_id ? { label: "Session", value: run.session_id } : null,
                          run.last_event ? { label: "Event", value: run.last_event } : null,
                          run.duration_ms != null
                            ? { label: "Duration", value: formatRuntimeDurationMs(run.duration_ms) }
                            : null,
                          run.total_tokens > 0
                            ? { label: "Tokens", value: compactNumber(run.total_tokens) }
                            : null,
                          run.last_message ? { label: "Last message", value: run.last_message } : null,
                        ].filter((row): row is { label: string; value: string } => row !== null);
                        return (
                          <div
                            key={run.run_id}
                            role="link"
                            tabIndex={0}
                            aria-label={`Open task ${run.task_title}`}
                            onClick={(event) => {
                              if (shouldIgnoreRowNavigation(event.target)) return;
                              router.push(buildRuntimeRunHref(run));
                            }}
                            onKeyDown={(event) => {
                              if (event.key !== "Enter" && event.key !== " ") return;
                              if (shouldIgnoreRowNavigation(event.target)) return;
                              event.preventDefault();
                              router.push(buildRuntimeRunHref(run));
                            }}
                            className="cursor-pointer rounded-lg border border-slate-200 bg-white px-3 py-2 transition hover:border-slate-300 focus-visible:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-medium text-slate-900">
                                  {run.task_title}
                                </p>
                                <p className="truncate text-xs text-slate-500">
                                  {run.board_name} ·
                                  {" "}
                                  <span className="inline-flex align-middle">
                                    <RuntimeRunStatusChip status={run.status} />
                                  </span>
                                  {" "}
                                  <span
                                    className={cn(
                                      "ml-1 inline-flex rounded-full border px-1.5 py-0.5 text-[10px] font-medium align-middle",
                                      operatorState.tone === "success" &&
                                        "border-emerald-200 bg-emerald-50 text-emerald-700",
                                      operatorState.tone === "warning" &&
                                        "border-amber-200 bg-amber-50 text-amber-700",
                                      operatorState.tone === "danger" &&
                                        "border-rose-200 bg-rose-50 text-rose-700",
                                      operatorState.tone === "neutral" &&
                                        "border-slate-200 bg-slate-50 text-slate-700",
                                    )}
                                  >
                                    {operatorState.label}
                                  </span>
                                  {run.branch_name ? ` · ${run.branch_name}` : ""}
                                </p>
                                <p className="mt-1 line-clamp-2 text-xs text-slate-600">
                                  {run.summary?.trim() || "No runtime summary yet."}
                                </p>
                                <div
                                  className={cn(
                                    "mt-2 rounded-md border px-2 py-2 text-left",
                                    guidance.tone === "success" &&
                                      "border-emerald-200 bg-emerald-50",
                                    guidance.tone === "warning" &&
                                      "border-amber-200 bg-amber-50",
                                    guidance.tone === "danger" &&
                                      "border-rose-200 bg-rose-50",
                                    guidance.tone === "neutral" &&
                                      "border-slate-200 bg-slate-50",
                                  )}
                                >
                                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                                    What next
                                  </p>
                                  <p className="mt-1 text-xs font-medium text-slate-900">
                                    {guidance.title}
                                  </p>
                                  <p className="mt-1 line-clamp-2 text-[11px] text-slate-600">
                                    {guidance.detail}
                                  </p>
                                  {runtimeRunNeedsApprovalAttention(run) &&
                                  (run.latest_approval_status === "approved" ||
                                    run.latest_approval_status === "rejected") ? (
                                    <div className="mt-2 rounded-md border border-slate-200 bg-white/70 px-2 py-2 text-[11px] text-slate-700">
                                      Latest approval was{" "}
                                      <span className="font-semibold">
                                        {run.latest_approval_status}
                                      </span>
                                      {run.latest_approval_resolved_at ? (
                                        <> {formatTimestamp(run.latest_approval_resolved_at)}</>
                                      ) : null}
                                      .{" "}
                                      {run.latest_approval_status === "approved"
                                        ? "Retry or continue the run now that the gate is clear."
                                        : "Review the rejection before retrying or escalating again."}
                                    </div>
                                  ) : null}
                                </div>
                                <RuntimeRunMetaGrid details={detailRows} itemKey={run.run_id} />
                              </div>
                              <div className="shrink-0 text-right">
                                <p className="text-xs font-medium text-slate-700">
                                  {compactNumber(run.total_tokens)} tokens
                                </p>
                                {duration ? (
                                  <p className="text-[11px] text-slate-500">
                                    {duration.label}: {duration.value}
                                  </p>
                                ) : null}
                                <p className="text-[11px] text-slate-500">
                                  {formatRelativeTimestamp(run.updated_at)}
                                </p>
                                {run.pr_url ? (
                                  <a
                                    href={run.pr_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="mt-1 inline-flex items-center gap-1 text-[11px] text-sky-700 hover:text-sky-800"
                                  >
                                    PR
                                    <ArrowUpRight className="h-3 w-3" />
                                  </a>
                                ) : null}
                                {canRetryRuntimeRun(run.status) ? (
                                  <button
                                    type="button"
                                    onClick={async (event) => {
                                      event.stopPropagation();
                                      await retryRuntimeRun(run);
                                    }}
                                    disabled={retryingRunId === run.run_id}
                                    className="mt-1 inline-flex items-center gap-1 text-[11px] text-amber-700 hover:text-amber-800"
                                  >
                                    {retryingRunId === run.run_id ? "Retrying…" : "Retry"}
                                  </button>
                                ) : null}
                                {canCancelRuntimeRun(run.status) ? (
                                  <button
                                    type="button"
                                    onClick={async (event) => {
                                      event.stopPropagation();
                                      await cancelRuntimeRun(run);
                                    }}
                                    disabled={cancellingRunId === run.run_id}
                                    className="mt-1 inline-flex items-center gap-1 text-[11px] text-rose-700 hover:text-rose-800"
                                  >
                                    {cancellingRunId === run.run_id ? "Cancelling…" : "Cancel"}
                                  </button>
                                ) : null}
                                {canAcknowledgeRuntimeRun(run.status) ? (
                                  <button
                                    type="button"
                                    onClick={async (event) => {
                                      event.stopPropagation();
                                      await acknowledgeRuntimeRun(run);
                                    }}
                                    disabled={acknowledgingRunId === run.run_id}
                                    className="mt-1 inline-flex items-center gap-1 text-[11px] text-emerald-700 hover:text-emerald-800"
                                  >
                                    {acknowledgingRunId === run.run_id
                                      ? "Acknowledging…"
                                      : "Acknowledge"}
                                  </button>
                                ) : null}
                                {canEscalateRuntimeRun(run.status) ? (
                                  <button
                                    type="button"
                                    onClick={async (event) => {
                                      event.stopPropagation();
                                      await escalateRuntimeRun(run);
                                    }}
                                    disabled={escalatingRunId === run.run_id}
                                    className="mt-1 inline-flex items-center gap-1 text-[11px] text-violet-700 hover:text-violet-800"
                                  >
                                    {escalatingRunId === run.run_id
                                      ? "Escalating…"
                                      : "Escalate"}
                                  </button>
                                ) : null}
                                {runtimeRunNeedsApprovalAttention(run) ? (
                                  <a
                                    href={`/boards/${encodeURIComponent(run.board_id)}/approvals`}
                                    onClick={(event) => event.stopPropagation()}
                                    className="mt-1 inline-flex items-center gap-1 text-[11px] text-violet-700 hover:text-violet-800"
                                  >
                                    {run.pending_approval_count && run.pending_approval_count > 0
                                      ? `Open approvals (${run.pending_approval_count})`
                                      : "Open approvals"}
                                    <ArrowUpRight className="h-3 w-3" />
                                  </a>
                                ) : null}
                              </div>
                            </div>
                          </div>
                        );
                      })()
                    ))
                  ) : (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
                      No recent execution runs.
                    </div>
                  )}
                </div>
              </section>
            </div>
          </div>
        </main>
      </SignedIn>
    </DashboardShell>
  );
}
