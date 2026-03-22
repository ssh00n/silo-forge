"use client";

import type {
  AgentActivityPayload,
  ApprovalActivityPayload,
  BoardActivityPayload,
  GatewayActivityPayload,
  QueueWorkerEventTelemetryPayload,
  SiloRuntimeActivityPayload,
  TaskActivityPayload,
  WebhookDeliveryResultTelemetryPayload,
} from "@/contracts/generated/schemas";
import {
  type RuntimeRunActivityPayload,
  type RuntimeRunStatus,
  parseRuntimeRunActivityPayload,
  resolveRuntimeRunFeedContent,
} from "@/lib/runtime-runs";

export type ActivityDetailRow = {
  label: string;
  value: string;
};

export type ActivityCategory =
  | "all"
  | "runs"
  | "runtime"
  | "tasks"
  | "approvals"
  | "boards"
  | "agents"
  | "gateway"
  | "chat";

const toRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || Array.isArray(value) || typeof value !== "object") return null;
  return value as Record<string, unknown>;
};

const hasString = (record: Record<string, unknown>, key: string): boolean => {
  const value = record[key];
  return typeof value === "string" && value.trim().length > 0;
};

const parseTaskActivityPayload = (payload: unknown): Partial<TaskActivityPayload> | null => {
  const record = toRecord(payload);
  if (!record) return null;
  if (!hasString(record, "task_title") && !hasString(record, "status")) {
    return null;
  }
  return record as Partial<TaskActivityPayload>;
};

const parseApprovalActivityPayload = (
  payload: unknown,
): Partial<ApprovalActivityPayload> | null => {
  const record = toRecord(payload);
  if (!record) return null;
  if (
    !hasString(record, "action_type") &&
    !hasString(record, "approval_status") &&
    !hasString(record, "notification_status")
  ) {
    return null;
  }
  return record as Partial<ApprovalActivityPayload>;
};

const parseAgentActivityPayload = (payload: unknown): Partial<AgentActivityPayload> | null => {
  const record = toRecord(payload);
  if (!record) return null;
  if (
    !hasString(record, "agent_name") &&
    !hasString(record, "action") &&
    !hasString(record, "delivery_status")
  ) {
    return null;
  }
  return record as Partial<AgentActivityPayload>;
};

const parseBoardActivityPayload = (payload: unknown): Partial<BoardActivityPayload> | null => {
  const record = toRecord(payload);
  if (!record) return null;
  if (
    !hasString(record, "notification_kind") &&
    !hasString(record, "board_name") &&
    !hasString(record, "target_agent_name")
  ) {
    return null;
  }
  return record as Partial<BoardActivityPayload>;
};

const parseGatewayActivityPayload = (
  payload: unknown,
): Partial<GatewayActivityPayload> | null => {
  const record = toRecord(payload);
  if (!record) return null;
  if (
    !hasString(record, "notification_kind") &&
    !hasString(record, "gateway_name") &&
    !hasString(record, "action")
  ) {
    return null;
  }
  return record as Partial<GatewayActivityPayload>;
};

const parseSiloRuntimeActivityPayload = (
  payload: unknown,
): Partial<SiloRuntimeActivityPayload> | null => {
  const record = toRecord(payload);
  if (!record) return null;
  if (
    !hasString(record, "silo_name") &&
    !hasString(record, "mode") &&
    !hasString(record, "operation_id")
  ) {
    return null;
  }
  return record as Partial<SiloRuntimeActivityPayload>;
};

const parseQueueWorkerTelemetryPayload = (
  payload: unknown,
): Partial<QueueWorkerEventTelemetryPayload> | null => {
  const record = toRecord(payload);
  if (!record) return null;
  if (!hasString(record, "queue_name") && !hasString(record, "status")) {
    return null;
  }
  return record as Partial<QueueWorkerEventTelemetryPayload>;
};

const parseWebhookTelemetryPayload = (
  payload: unknown,
): Partial<WebhookDeliveryResultTelemetryPayload> | null => {
  const record = toRecord(payload);
  if (!record) return null;
  if (!hasString(record, "status") && !hasString(record, "payload_id")) {
    return null;
  }
  return record as Partial<WebhookDeliveryResultTelemetryPayload>;
};

const parseSiloRequestPayload = (
  payload: unknown,
): Record<string, unknown> | null => {
  const record = toRecord(payload);
  if (!record) return null;
  if (!hasString(record, "display_name") && !hasString(record, "status")) {
    return null;
  }
  return record;
};

const resolveBoardActivityContent = (
  eventType: string,
  message: string,
  payload: Partial<BoardActivityPayload> | null,
): { summary: string; details: ActivityDetailRow[] } | null => {
  if (!payload) return null;
  const notificationKind = payload.notification_kind?.trim() || null;
  const notificationStatus = payload.notification_status?.trim() || null;
  const targetAgentName = payload.target_agent_name?.trim() || null;
  const boardName = payload.board_name?.trim() || null;
  const sourceBoardName = payload.source_board_name?.trim() || null;
  const groupName = payload.board_group_name?.trim() || null;
  const error = payload.error?.trim() || null;

  const details: ActivityDetailRow[] = [];
  if (notificationKind) details.push({ label: "Kind", value: notificationKind });
  if (notificationStatus) details.push({ label: "Notify", value: notificationStatus });
  if (targetAgentName) details.push({ label: "Agent", value: targetAgentName });
  if (boardName) details.push({ label: "Board", value: boardName });
  if (sourceBoardName) details.push({ label: "Source", value: sourceBoardName });
  if (groupName) details.push({ label: "Group", value: groupName });
  if (error) details.push({ label: "Error", value: error });

  const fallbackSummary =
    eventType.startsWith("board.") && notificationKind && boardName
      ? `${notificationKind.replace(/_/g, " ")} on ${boardName}.`
      : null;

  if (details.length === 0 && !fallbackSummary) return null;
  return { summary: message || fallbackSummary || eventType, details };
};

const resolveGatewayActivityContent = (
  eventType: string,
  message: string,
  payload: Partial<GatewayActivityPayload> | null,
  agentPayload: Partial<AgentActivityPayload> | null = null,
  rawPayload: Record<string, unknown> | null = null,
): { summary: string; details: ActivityDetailRow[] } | null => {
  if (!payload) return null;
  const notificationKind = payload.notification_kind?.trim() || null;
  const notificationStatus =
    payload.notification_status?.trim() || payload.delivery_status?.trim() || null;
  const targetAgentName =
    agentPayload?.agent_name?.trim() ||
    payload.target_agent_name?.trim() ||
    readString(rawPayload, ["agent_name"]) ||
    null;
  const boardName = payload.board_name?.trim() || null;
  const gatewayName =
    payload.gateway_name?.trim() || readString(rawPayload, ["gateway_name"]) || null;
  const action = payload.action?.trim() || readString(rawPayload, ["action"]) || null;
  const targetKind =
    payload.target_kind?.trim() || readString(rawPayload, ["target_kind"]) || null;
  const workspacePath =
    payload.workspace_path?.trim() ||
    readString(rawPayload, ["workspace_path"]) ||
    null;
  const sessionKey =
    agentPayload?.session_key?.trim() ||
    payload.session_key?.trim() ||
    readString(rawPayload, ["session_key"]) ||
    null;
  const error =
    agentPayload?.error?.trim() || payload.error?.trim() || readString(rawPayload, ["error"]) || null;

  const details: ActivityDetailRow[] = [];
  if (eventType.startsWith("agent.")) {
    if (targetAgentName) details.push({ label: "Agent", value: targetAgentName });
    if (action) details.push({ label: "Action", value: action });
    if (notificationStatus) details.push({ label: "Delivery", value: notificationStatus });
    if (gatewayName) details.push({ label: "Gateway", value: gatewayName });
  } else {
    if (notificationKind) details.push({ label: "Kind", value: notificationKind });
    if (notificationStatus) details.push({ label: "Notify", value: notificationStatus });
    if (targetAgentName) details.push({ label: "Agent", value: targetAgentName });
    if (boardName) details.push({ label: "Board", value: boardName });
    if (gatewayName) details.push({ label: "Gateway", value: gatewayName });
    if (action) details.push({ label: "Action", value: action });
  }
  if (targetKind) details.push({ label: "Target", value: targetKind });
  if (workspacePath) details.push({ label: "Workspace", value: workspacePath });
  if (sessionKey) details.push({ label: "Session", value: sessionKey });
  if (error) details.push({ label: "Error", value: error });

  const fallbackSummary =
    (eventType.startsWith("gateway.") || eventType.startsWith("agent.")) &&
    (action || notificationKind)
      ? `${action ?? notificationKind} ${notificationStatus ?? "event"}.`
      : null;

  if (details.length === 0 && !fallbackSummary) return null;
  return { summary: message || fallbackSummary || eventType, details };
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
      const parsed = Number.parseFloat(value.trim());
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return null;
};

export const resolveActivityFeedContent = (
  eventType: string,
  message: string | null | undefined,
  payload: unknown,
): { summary: string; details: ActivityDetailRow[]; runtimeStatus: RuntimeRunStatus | null } => {
  const normalizedMessage = (message ?? "").trim();
  const normalizedPayload = toRecord(payload);

  if (eventType.startsWith("task.execution_run.")) {
    const runtime = resolveRuntimeRunFeedContent(
      eventType,
      normalizedMessage,
      normalizedPayload,
    );
    return {
      summary: runtime.summary,
      details: runtime.details,
      runtimeStatus: runtime.status,
    };
  }

  if (
    eventType === "task.created" ||
    eventType === "task.updated" ||
    eventType === "task.status_changed"
  ) {
    const taskPayload = parseTaskActivityPayload(normalizedPayload);
    const taskTitle = taskPayload?.task_title?.trim() || "Task";
    const status = taskPayload?.status?.trim() || null;
    const previousStatus = taskPayload?.previous_status?.trim() || null;
    const reason = taskPayload?.reason?.trim() || null;
    const dependencyTaskTitle = taskPayload?.dependency_task_title?.trim() || null;

    const details: ActivityDetailRow[] = [];
    if (status) details.push({ label: "Status", value: status });
    if (previousStatus) details.push({ label: "Previous", value: previousStatus });
    if (dependencyTaskTitle) details.push({ label: "Dependency", value: dependencyTaskTitle });
    if (reason) details.push({ label: "Reason", value: reason });

    let summary = normalizedMessage || eventType;
    if (eventType === "task.created") {
      summary = `Task created: ${taskTitle}.`;
    } else if (eventType === "task.status_changed" && status) {
      summary = `Task moved to ${status}: ${taskTitle}.`;
    } else if (eventType === "task.updated") {
      summary = `Task updated: ${taskTitle}.`;
    }
    return { summary, details, runtimeStatus: null };
  }

  if (eventType.startsWith("approval.")) {
    const approvalPayload = parseApprovalActivityPayload(normalizedPayload);
    const approvalStatus = approvalPayload?.approval_status?.trim() || null;
    const actionType = approvalPayload?.action_type?.trim() || null;
    const notificationStatus = approvalPayload?.notification_status?.trim() || null;
    const error = approvalPayload?.error?.trim() || null;
    const details: ActivityDetailRow[] = [];
    if (approvalStatus) details.push({ label: "Decision", value: approvalStatus });
    if (actionType) details.push({ label: "Action", value: actionType });
    if (notificationStatus) details.push({ label: "Notify", value: notificationStatus });
    if (error) details.push({ label: "Error", value: error });
    return {
      summary: normalizedMessage || `${eventType.replace(/\./g, " ")}.`,
      details,
      runtimeStatus: null,
    };
  }

  if (eventType.startsWith("agent.")) {
    const agentPayload = parseAgentActivityPayload(normalizedPayload);
    const gatewayPayload = parseGatewayActivityPayload(normalizedPayload);
    const resolved =
      resolveGatewayActivityContent(
        eventType,
        normalizedMessage,
        gatewayPayload,
        agentPayload,
        normalizedPayload,
      ) ??
      (() => {
        const agentName = agentPayload?.agent_name?.trim() || readString(normalizedPayload, ["agent_name"]);
        const action = agentPayload?.action?.trim() || readString(normalizedPayload, ["action"]);
        const deliveryStatus =
          agentPayload?.delivery_status?.trim() || readString(normalizedPayload, ["delivery_status"]);
        const gatewayName =
          agentPayload?.gateway_name?.trim() || readString(normalizedPayload, ["gateway_name"]);
        const targetKind =
          agentPayload?.target_kind?.trim() || readString(normalizedPayload, ["target_kind"]);
        const workspacePath =
          agentPayload?.workspace_path?.trim() || readString(normalizedPayload, ["workspace_path"]);
        const sessionKey =
          agentPayload?.session_key?.trim() || readString(normalizedPayload, ["session_key"]);
        const error = agentPayload?.error?.trim() || readString(normalizedPayload, ["error"]);
        const details: ActivityDetailRow[] = [];
        if (agentName) details.push({ label: "Agent", value: agentName });
        if (action) details.push({ label: "Action", value: action });
        if (deliveryStatus) details.push({ label: "Delivery", value: deliveryStatus });
        if (gatewayName) details.push({ label: "Gateway", value: gatewayName });
        if (targetKind) details.push({ label: "Target", value: targetKind });
        if (workspacePath) details.push({ label: "Workspace", value: workspacePath });
        if (sessionKey) details.push({ label: "Session", value: sessionKey });
        if (error) details.push({ label: "Error", value: error });
        return { summary: normalizedMessage || eventType, details };
      })();
    return { ...resolved, runtimeStatus: null };
  }

  if (eventType.startsWith("task.") && normalizedPayload) {
    const taskPayload = parseTaskActivityPayload(normalizedPayload);
    const taskTitle = taskPayload?.task_title?.trim() || null;
    const targetAgentName = taskPayload?.target_agent_name?.trim() || null;
    const notificationKind = taskPayload?.notification_kind?.trim() || null;
    const notificationStatus = taskPayload?.notification_status?.trim() || null;
    const error = taskPayload?.error?.trim() || null;
    const status = taskPayload?.status?.trim() || null;
    const details: ActivityDetailRow[] = [];
    if (taskTitle) details.push({ label: "Task", value: taskTitle });
    if (targetAgentName) details.push({ label: "Agent", value: targetAgentName });
    if (notificationKind) details.push({ label: "Kind", value: notificationKind });
    if (notificationStatus) details.push({ label: "Notify", value: notificationStatus });
    if (status) details.push({ label: "Status", value: status });
    if (error) details.push({ label: "Error", value: error });
    return {
      summary: normalizedMessage || eventType,
      details,
      runtimeStatus: null,
    };
  }

  if (eventType.startsWith("silo.runtime.")) {
    const runtimePayload = parseSiloRuntimeActivityPayload(normalizedPayload);
    const siloName = runtimePayload?.silo_name?.trim() || readString(normalizedPayload, ["silo_name"]);
    const mode = runtimePayload?.mode?.trim() || readString(normalizedPayload, ["mode"]);
    const operationId =
      runtimePayload?.operation_id?.trim() || readString(normalizedPayload, ["operation_id"]);
    const resultCount =
      runtimePayload?.result_count?.trim() || readString(normalizedPayload, ["result_count"]);
    const warningCount =
      runtimePayload?.warning_count?.trim() || readString(normalizedPayload, ["warning_count"]);
    const restartRequired =
      runtimePayload?.restart_required?.trim() ||
      readString(normalizedPayload, ["restart_required"]);
    const gatewayNames =
      runtimePayload?.gateway_names?.trim() || readString(normalizedPayload, ["gateway_names"]);
    const roles = runtimePayload?.roles?.trim() || readString(normalizedPayload, ["roles"]);

    const details: ActivityDetailRow[] = [];
    if (siloName) details.push({ label: "Silo", value: siloName });
    if (mode) details.push({ label: "Mode", value: mode });
    if (resultCount) details.push({ label: "Results", value: resultCount });
    if (warningCount) details.push({ label: "Warnings", value: warningCount });
    if (restartRequired) details.push({ label: "Restart", value: restartRequired });
    if (gatewayNames) details.push({ label: "Gateways", value: gatewayNames });
    if (roles) details.push({ label: "Roles", value: roles });
    if (operationId) details.push({ label: "Operation", value: operationId });
    return {
      summary: normalizedMessage || eventType,
      details,
      runtimeStatus: null,
    };
  }

  if (eventType.startsWith("silo.request.")) {
    const requestPayload = parseSiloRequestPayload(normalizedPayload);
    const displayName = readString(requestPayload, ["display_name"]) ?? "Silo request";
    const status = readString(requestPayload, ["status"]);
    const previousStatus = readString(requestPayload, ["previous_status"]);
    const priority = readString(requestPayload, ["priority"]);
    const scope = readString(requestPayload, ["scope"]);
    const siloKind = readString(requestPayload, ["silo_kind"]);
    const sourceTaskTitle = readString(requestPayload, ["source_task_title"]);
    const materializedSiloSlug = readString(requestPayload, ["materialized_silo_slug"]);
    const details: ActivityDetailRow[] = [];
    if (status) details.push({ label: "Status", value: status });
    if (previousStatus) details.push({ label: "Previous", value: previousStatus });
    if (priority) details.push({ label: "Priority", value: priority });
    if (scope) details.push({ label: "Scope", value: scope });
    if (siloKind) details.push({ label: "Shape", value: siloKind });
    if (sourceTaskTitle) details.push({ label: "Demand", value: sourceTaskTitle });
    if (materializedSiloSlug) details.push({ label: "Silo", value: materializedSiloSlug });
    return {
      summary: normalizedMessage || `Silo request updated: ${displayName}.`,
      details,
      runtimeStatus: null,
    };
  }

  if (eventType.startsWith("queue.worker.")) {
    const telemetry = parseQueueWorkerTelemetryPayload(normalizedPayload);
    const queueName = telemetry?.queue_name?.trim() || readString(normalizedPayload, ["queue_name"]);
    const status = telemetry?.status?.trim() || readString(normalizedPayload, ["status"]);
    const taskType = telemetry?.task_type?.trim() || readString(normalizedPayload, ["task_type"]);
    const attempt = telemetry?.attempt ?? readNumber(normalizedPayload, ["attempt"]);
    const count = telemetry?.count ?? readNumber(normalizedPayload, ["count"]);
    const throttleSeconds =
      telemetry?.throttle_seconds ?? readNumber(normalizedPayload, ["throttle_seconds"]);
    const retryDelaySeconds =
      telemetry?.retry_delay_seconds ?? readNumber(normalizedPayload, ["retry_delay_seconds"]);
    const error = telemetry?.error?.trim() || readString(normalizedPayload, ["error"]);
    const details: ActivityDetailRow[] = [];
    if (queueName) details.push({ label: "Queue", value: queueName });
    if (status) details.push({ label: "Status", value: status });
    if (taskType) details.push({ label: "Task type", value: taskType });
    if (attempt !== null && attempt !== undefined) details.push({ label: "Attempt", value: String(attempt) });
    if (count !== null && count !== undefined) details.push({ label: "Count", value: String(count) });
    if (throttleSeconds !== null && throttleSeconds !== undefined) {
      details.push({ label: "Throttle", value: `${throttleSeconds}s` });
    }
    if (retryDelaySeconds !== null && retryDelaySeconds !== undefined) {
      details.push({ label: "Retry", value: `${retryDelaySeconds}s` });
    }
    if (error) details.push({ label: "Error", value: error });
    return {
      summary: normalizedMessage || (status ? `Queue worker ${status}.` : eventType),
      details,
      runtimeStatus: null,
    };
  }

  if (eventType.startsWith("webhook.dispatch.")) {
    const telemetry = parseWebhookTelemetryPayload(normalizedPayload);
    const status = telemetry?.status?.trim() || readString(normalizedPayload, ["status"]);
    const payloadId = telemetry?.payload_id?.trim() || readString(normalizedPayload, ["payload_id"]);
    const webhookId = telemetry?.webhook_id?.trim() || readString(normalizedPayload, ["webhook_id"]);
    const attempt = telemetry?.attempt ?? readNumber(normalizedPayload, ["attempt"]);
    const count = telemetry?.count ?? readNumber(normalizedPayload, ["count"]);
    const durationMs = telemetry?.duration_ms ?? readNumber(normalizedPayload, ["duration_ms"]);
    const throttleSeconds =
      telemetry?.throttle_seconds ?? readNumber(normalizedPayload, ["throttle_seconds"]);
    const retryDelaySeconds =
      telemetry?.retry_delay_seconds ?? readNumber(normalizedPayload, ["retry_delay_seconds"]);
    const error = telemetry?.error?.trim() || readString(normalizedPayload, ["error"]);
    const details: ActivityDetailRow[] = [];
    if (status) details.push({ label: "Status", value: status });
    if (payloadId) details.push({ label: "Payload", value: payloadId });
    if (webhookId) details.push({ label: "Webhook", value: webhookId });
    if (attempt !== null && attempt !== undefined) details.push({ label: "Attempt", value: String(attempt) });
    if (count !== null && count !== undefined) details.push({ label: "Count", value: String(count) });
    if (durationMs !== null && durationMs !== undefined) details.push({ label: "Duration", value: `${durationMs}ms` });
    if (throttleSeconds !== null && throttleSeconds !== undefined) {
      details.push({ label: "Throttle", value: `${throttleSeconds}s` });
    }
    if (retryDelaySeconds !== null && retryDelaySeconds !== undefined) {
      details.push({ label: "Retry", value: `${retryDelaySeconds}s` });
    }
    if (error) details.push({ label: "Error", value: error });
    return {
      summary: normalizedMessage || (status ? `Webhook dispatch ${status}.` : eventType),
      details,
      runtimeStatus: null,
    };
  }

  if (normalizedPayload) {
    const boardPayload = parseBoardActivityPayload(normalizedPayload);
    const gatewayPayload = parseGatewayActivityPayload(normalizedPayload);
    const agentPayload = parseAgentActivityPayload(normalizedPayload);
    if (eventType.startsWith("board.")) {
      const resolvedBoard = resolveBoardActivityContent(
        eventType,
        normalizedMessage,
        boardPayload,
      );
      if (resolvedBoard) {
        return { ...resolvedBoard, runtimeStatus: null };
      }
    }
    const resolvedGateway = resolveGatewayActivityContent(
      eventType,
      normalizedMessage,
      gatewayPayload,
      agentPayload,
      normalizedPayload,
    );
    if (resolvedGateway) {
      return { ...resolvedGateway, runtimeStatus: null };
    }
    const notificationKind =
      boardPayload?.notification_kind?.trim() ||
      gatewayPayload?.notification_kind?.trim() ||
      readString(normalizedPayload, ["notification_kind"]);
    const notificationStatus =
      boardPayload?.notification_status?.trim() ||
      gatewayPayload?.notification_status?.trim() ||
      readString(normalizedPayload, ["notification_status"]);
    const targetAgentName =
      boardPayload?.target_agent_name?.trim() ||
      gatewayPayload?.target_agent_name?.trim() ||
      readString(normalizedPayload, ["target_agent_name"]);
    const boardName =
      boardPayload?.board_name?.trim() ||
      gatewayPayload?.board_name?.trim() ||
      readString(normalizedPayload, ["board_name"]);
    const sourceBoardName =
      boardPayload?.source_board_name?.trim() ||
      readString(normalizedPayload, ["source_board_name"]);
    const groupName =
      boardPayload?.board_group_name?.trim() ||
      readString(normalizedPayload, ["board_group_name"]);
    const error =
      boardPayload?.error?.trim() ||
      gatewayPayload?.error?.trim() ||
      readString(normalizedPayload, ["error"]);

    const details: ActivityDetailRow[] = [];
    if (notificationKind) details.push({ label: "Kind", value: notificationKind });
    if (notificationStatus) details.push({ label: "Notify", value: notificationStatus });
    if (targetAgentName) details.push({ label: "Agent", value: targetAgentName });
    if (boardName) details.push({ label: "Board", value: boardName });
    if (sourceBoardName) details.push({ label: "Source", value: sourceBoardName });
    if (groupName) details.push({ label: "Group", value: groupName });
    if (error) details.push({ label: "Error", value: error });

    if (details.length > 0) {
      return {
        summary: normalizedMessage || eventType,
        details,
        runtimeStatus: null,
      };
    }
  }

  return {
    summary: normalizedMessage || eventType,
    details: [],
    runtimeStatus: null,
  };
};

export const parseExecutionRunActivityPayload = (
  payload: unknown,
): RuntimeRunActivityPayload | null => parseRuntimeRunActivityPayload(payload);

export const activityCategoryForEvent = (eventType: string): ActivityCategory => {
  if (eventType.startsWith("task.execution_run.")) return "runs";
  if (eventType === "board.chat" || eventType === "board.command") return "chat";
  if (eventType.startsWith("task.")) return "tasks";
  if (eventType.startsWith("approval.")) return "approvals";
  if (eventType.startsWith("silo.request.")) return "boards";
  if (eventType.startsWith("silo.runtime.")) return "runtime";
  if (eventType.startsWith("queue.worker.")) return "runtime";
  if (eventType.startsWith("webhook.dispatch.")) return "gateway";
  if (eventType.startsWith("gateway.")) return "gateway";
  if (eventType.startsWith("board.")) return "boards";
  if (eventType.startsWith("agent.")) return "agents";
  return "all";
};
