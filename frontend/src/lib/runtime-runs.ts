"use client";

import { parseApiDatetime } from "@/lib/datetime";
import { parseTimestamp } from "@/lib/formatters";

export type RuntimeRunStatus =
  | "queued"
  | "dispatching"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "blocked";

export type RuntimeRunSnapshot = {
  id: string;
  board_id: string;
  task_id: string;
  status: RuntimeRunStatus | string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at: string;
  summary?: string | null;
  branch_name?: string | null;
  pr_url?: string | null;
};

export type RuntimeRunActivityPayload = {
  executor_kind?: string;
  run_id?: string;
  run_short_id?: string;
  organization_id?: string;
  board_id?: string;
  task_id?: string;
  silo_id?: string;
  silo_slug?: string;
  role_slug?: string;
  status?: string;
  adapter_mode?: string;
  branch_hint?: string;
  branch_name?: string;
  workspace_path?: string;
  external_run_id?: string;
  summary?: string;
  pr_url?: string;
  pull_request?: number;
  total_tokens?: number;
  error_message?: string;
  has_prompt_override?: boolean;
  retried_from_run_id?: string;
};

export type TaskExecutionRunSnapshot = RuntimeRunSnapshot & {
  organization_id: string;
  silo_id: string;
  silo_slug: string;
  requested_by_user_id?: string | null;
  requested_by_agent_id?: string | null;
  executor_kind: "symphony";
  role_slug: string;
  task_snapshot?: Record<string, unknown> | null;
  dispatch_payload?: Record<string, unknown> | null;
  result_payload?: Record<string, unknown> | null;
  external_run_id?: string | null;
  workspace_path?: string | null;
  error_message?: string | null;
};

export type TaskExecutionRunsResponse = {
  data: TaskExecutionRunSnapshot[];
  status: number;
  headers: Headers;
};

export type TaskExecutionRunResponse = {
  data: TaskExecutionRunSnapshot;
  status: number;
  headers: Headers;
};

const parseRunTimestamp = (value?: string | null): number | null => {
  if (!value) return null;
  const parsed =
    parseApiDatetime(value)?.getTime() ?? parseTimestamp(value)?.getTime() ?? null;
  return Number.isFinite(parsed) ? parsed : null;
};

export const runtimeRunStatusClass = (status: string): string => {
  if (status === "succeeded") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (status === "running") return "border-sky-200 bg-sky-50 text-sky-700";
  if (status === "dispatching") return "border-indigo-200 bg-indigo-50 text-indigo-700";
  if (status === "queued") return "border-amber-200 bg-amber-50 text-amber-700";
  if (status === "failed") return "border-rose-200 bg-rose-50 text-rose-700";
  if (status === "cancelled") return "border-slate-300 bg-slate-100 text-slate-700";
  if (status === "blocked") return "border-orange-200 bg-orange-50 text-orange-700";
  return "border-slate-200 bg-slate-100 text-slate-700";
};

export const formatRuntimeDurationMs = (value: number): string => {
  if (!Number.isFinite(value) || value <= 0) return "—";
  const totalSeconds = Math.floor(value / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const totalMinutes = Math.floor(totalSeconds / 60);
  if (totalMinutes < 60) {
    const seconds = totalSeconds % 60;
    return seconds > 0 ? `${totalMinutes}m ${seconds}s` : `${totalMinutes}m`;
  }
  const totalHours = Math.floor(totalMinutes / 60);
  if (totalHours < 24) {
    const minutes = totalMinutes % 60;
    return minutes > 0 ? `${totalHours}h ${minutes}m` : `${totalHours}h`;
  }
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  return hours > 0 ? `${days}d ${hours}h` : `${days}d`;
};

export const runtimeRunTimingRows = (
  run: RuntimeRunSnapshot,
): Array<{ label: string; value: string }> => {
  const now = Date.now();
  const createdAt = parseRunTimestamp(run.created_at);
  const startedAt = parseRunTimestamp(run.started_at);
  const completedAt = parseRunTimestamp(run.completed_at);
  const rows: Array<{ label: string; value: string }> = [];

  if ((run.status === "queued" || run.status === "blocked") && createdAt !== null) {
    rows.push({ label: "Queued for", value: formatRuntimeDurationMs(now - createdAt) });
  }
  if (run.status === "dispatching" && startedAt !== null) {
    rows.push({ label: "Dispatching for", value: formatRuntimeDurationMs(now - startedAt) });
  }
  if (run.status === "running" && startedAt !== null) {
    rows.push({ label: "Running for", value: formatRuntimeDurationMs(now - startedAt) });
  }
  if (completedAt !== null && createdAt !== null) {
    rows.push({
      label: "Completed in",
      value: formatRuntimeDurationMs(completedAt - createdAt),
    });
  }
  return rows;
};

export const runtimeRunTimingLabel = (
  run: RuntimeRunSnapshot,
): { label: string; value: string } | null => runtimeRunTimingRows(run)[0] ?? null;

export const extractRuntimeRunMessageParts = (message: string) => {
  const detailLabels = [
    "PR #",
    "PR:",
    "Tokens:",
    "Branch:",
    "Workspace:",
    "External run:",
    "Error:",
  ];
  const summary: string[] = [];
  const details: Array<{ label: string; value: string }> = [];

  for (const rawLine of message.split("\n")) {
    const line = rawLine.trim();
    if (!line) continue;
    const matchedLabel = detailLabels.find((label) => line.startsWith(label));
    if (!matchedLabel) {
      summary.push(line);
      continue;
    }
    details.push({
      label: matchedLabel.replace(/:$/, ""),
      value: line.slice(matchedLabel.length).trim() || "—",
    });
  }

  return {
    summary: summary.join("\n"),
    details,
  };
};

export const parseRuntimeRunActivityPayload = (
  payload: unknown,
): RuntimeRunActivityPayload | null => {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;
  return payload as RuntimeRunActivityPayload;
};

export const extractRuntimeRunDetailsFromPayload = (
  payload: unknown,
): Array<{ label: string; value: string }> => {
  const parsed = parseRuntimeRunActivityPayload(payload);
  if (!parsed) return [];
  const details: Array<{ label: string; value: string }> = [];

  if (typeof parsed.pull_request === "number" && Number.isFinite(parsed.pull_request)) {
    details.push({ label: "PR #", value: String(Math.trunc(parsed.pull_request)) });
  }
  if (typeof parsed.pr_url === "string" && parsed.pr_url.trim()) {
    details.push({ label: "PR", value: parsed.pr_url.trim() });
  }
  if (typeof parsed.branch_name === "string" && parsed.branch_name.trim()) {
    details.push({ label: "Branch", value: parsed.branch_name.trim() });
  } else if (typeof parsed.branch_hint === "string" && parsed.branch_hint.trim()) {
    details.push({ label: "Branch", value: parsed.branch_hint.trim() });
  }
  if (typeof parsed.workspace_path === "string" && parsed.workspace_path.trim()) {
    details.push({ label: "Workspace", value: parsed.workspace_path.trim() });
  }
  if (typeof parsed.external_run_id === "string" && parsed.external_run_id.trim()) {
    details.push({ label: "External run", value: parsed.external_run_id.trim() });
  }
  if (typeof parsed.total_tokens === "number" && Number.isFinite(parsed.total_tokens)) {
    details.push({ label: "Tokens", value: new Intl.NumberFormat("en-US").format(parsed.total_tokens) });
  }
  if (typeof parsed.error_message === "string" && parsed.error_message.trim()) {
    details.push({ label: "Error", value: parsed.error_message.trim() });
  }
  return details;
};

export const runtimeRunSummaryFromPayload = (payload: unknown): string | null => {
  const parsed = parseRuntimeRunActivityPayload(payload);
  if (!parsed || typeof parsed.summary !== "string") return null;
  const trimmed = parsed.summary.trim();
  return trimmed || null;
};

export const runtimeRunFallbackSummary = (
  eventType: string,
  payload: unknown,
): string | null => {
  const parsed = parseRuntimeRunActivityPayload(payload);
  if (!parsed) return null;

  const runShortId =
    typeof parsed.run_short_id === "string" && parsed.run_short_id.trim()
      ? parsed.run_short_id.trim()
      : typeof parsed.run_id === "string" && parsed.run_id.trim()
        ? parsed.run_id.trim().slice(0, 8)
        : null;
  const status =
    typeof parsed.status === "string" && parsed.status.trim() ? parsed.status.trim() : null;
  const siloSlug =
    typeof parsed.silo_slug === "string" && parsed.silo_slug.trim()
      ? parsed.silo_slug.trim()
      : null;
  const roleSlug =
    typeof parsed.role_slug === "string" && parsed.role_slug.trim()
      ? parsed.role_slug.trim()
      : null;

  if (eventType === "task.execution_run.created") {
    const destination = siloSlug && roleSlug ? `${siloSlug}/${roleSlug}` : roleSlug ?? siloSlug;
    if (runShortId && destination) return `Queued Symphony run \`${runShortId}\` for ${destination}.`;
    if (runShortId) return `Queued Symphony run \`${runShortId}\`.`;
    if (destination) return `Queued Symphony run for ${destination}.`;
    return "Queued Symphony run.";
  }

  if (eventType === "task.execution_run.retried") {
    const originalRunId =
      typeof parsed.retried_from_run_id === "string" && parsed.retried_from_run_id.trim()
        ? parsed.retried_from_run_id.trim().slice(0, 8)
        : null;
    if (originalRunId && runShortId) {
      return `Retried Symphony run \`${originalRunId}\` as \`${runShortId}\`.`;
    }
    if (runShortId) return `Retried Symphony run as \`${runShortId}\`.`;
    return "Retried Symphony run.";
  }

  if (eventType === "task.execution_run.dispatched") {
    const adapterMode =
      typeof parsed.adapter_mode === "string" && parsed.adapter_mode.trim()
        ? parsed.adapter_mode.trim()
        : null;
    if (runShortId && adapterMode) {
      return `Dispatched Symphony run \`${runShortId}\` via ${adapterMode} adapter.`;
    }
    if (runShortId) return `Dispatched Symphony run \`${runShortId}\`.`;
    return "Dispatched Symphony run.";
  }

  if (eventType === "task.execution_run.updated" || eventType === "task.execution_run.report") {
    if (runShortId && status) {
      return `Symphony run \`${runShortId}\` is ${status}.`;
    }
    if (status) return `Symphony run is ${status}.`;
    if (runShortId) return `Symphony run \`${runShortId}\` updated.`;
  }

  return null;
};

export const resolveRuntimeRunFeedContent = (
  eventType: string,
  message: string | null | undefined,
  payload: unknown,
): {
  status: string | null;
  summary: string;
  details: Array<{ label: string; value: string }>;
} => {
  const normalizedMessage = (message ?? "").trim();
  const parsedMessage = normalizedMessage ? extractRuntimeRunMessageParts(normalizedMessage) : null;
  const details = extractRuntimeRunDetailsFromPayload(payload);
  return {
    status: inferRuntimeRunStatusFromEvent(eventType, normalizedMessage, payload),
    summary:
      runtimeRunSummaryFromPayload(payload) ??
      runtimeRunFallbackSummary(eventType, payload) ??
      parsedMessage?.summary ??
      normalizedMessage,
    details: details.length > 0 ? details : (parsedMessage?.details ?? []),
  };
};

export const inferRuntimeRunStatusFromEvent = (
  eventType: string,
  message?: string | null,
  payload?: unknown,
): string | null => {
  const parsedPayload = parseRuntimeRunActivityPayload(payload);
  if (typeof parsedPayload?.status === "string" && parsedPayload.status.trim()) {
    return parsedPayload.status.trim();
  }
  if (eventType === "task.execution_run.created") return "queued";
  if (eventType === "task.execution_run.retried") return "queued";
  if (eventType === "task.execution_run.dispatched") return "dispatching";

  const normalized = (message ?? "").toLowerCase();
  const knownStatuses = [
    "succeeded",
    "failed",
    "cancelled",
    "blocked",
    "running",
    "dispatching",
    "queued",
  ];
  for (const status of knownStatuses) {
    if (normalized.includes(` ${status} `) || normalized.startsWith(status) || normalized.includes(`${status}.`)) {
      return status;
    }
  }
  return null;
};
