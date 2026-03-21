"use client";

import { resolveRuntimeRunFeedContent } from "@/lib/runtime-runs";

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

export const resolveActivityFeedContent = (
  eventType: string,
  message: string | null | undefined,
  payload: unknown,
): { summary: string; details: ActivityDetailRow[]; runtimeStatus: string | null } => {
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
    const taskTitle = readString(normalizedPayload, ["task_title"]) ?? "Task";
    const status = readString(normalizedPayload, ["status"]);
    const previousStatus = readString(normalizedPayload, ["previous_status"]);
    const reason = readString(normalizedPayload, ["reason"]);
    const dependencyTaskTitle = readString(normalizedPayload, ["dependency_task_title"]);

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
    const approvalStatus = readString(normalizedPayload, ["approval_status"]);
    const actionType = readString(normalizedPayload, ["action_type"]);
    const notificationStatus = readString(normalizedPayload, ["notification_status"]);
    const error = readString(normalizedPayload, ["error"]);
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
    const agentName = readString(normalizedPayload, ["agent_name"]);
    const action = readString(normalizedPayload, ["action"]);
    const deliveryStatus = readString(normalizedPayload, ["delivery_status"]);
    const gatewayName = readString(normalizedPayload, ["gateway_name"]);
    const targetKind = readString(normalizedPayload, ["target_kind"]);
    const workspacePath = readString(normalizedPayload, ["workspace_path"]);
    const sessionKey = readString(normalizedPayload, ["session_key"]);
    const error = readString(normalizedPayload, ["error"]);

    const details: ActivityDetailRow[] = [];
    if (agentName) details.push({ label: "Agent", value: agentName });
    if (action) details.push({ label: "Action", value: action });
    if (deliveryStatus) details.push({ label: "Delivery", value: deliveryStatus });
    if (gatewayName) details.push({ label: "Gateway", value: gatewayName });
    if (targetKind) details.push({ label: "Target", value: targetKind });
    if (workspacePath) details.push({ label: "Workspace", value: workspacePath });
    if (sessionKey) details.push({ label: "Session", value: sessionKey });
    if (error) details.push({ label: "Error", value: error });
    return {
      summary: normalizedMessage || eventType,
      details,
      runtimeStatus: null,
    };
  }

  if (eventType.startsWith("task.") && normalizedPayload) {
    const taskTitle = readString(normalizedPayload, ["task_title"]);
    const targetAgentName = readString(normalizedPayload, ["target_agent_name"]);
    const notificationKind = readString(normalizedPayload, ["notification_kind"]);
    const notificationStatus = readString(normalizedPayload, ["notification_status"]);
    const error = readString(normalizedPayload, ["error"]);
    const status = readString(normalizedPayload, ["status"]);
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
    const siloName = readString(normalizedPayload, ["silo_name"]);
    const mode = readString(normalizedPayload, ["mode"]);
    const operationId = readString(normalizedPayload, ["operation_id"]);
    const resultCount = readString(normalizedPayload, ["result_count"]);
    const warningCount = readString(normalizedPayload, ["warning_count"]);
    const restartRequired = readString(normalizedPayload, ["restart_required"]);
    const gatewayNames = readString(normalizedPayload, ["gateway_names"]);
    const roles = readString(normalizedPayload, ["roles"]);

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

  if (normalizedPayload) {
    const notificationKind = readString(normalizedPayload, ["notification_kind"]);
    const notificationStatus = readString(normalizedPayload, ["notification_status"]);
    const targetAgentName = readString(normalizedPayload, ["target_agent_name"]);
    const boardName = readString(normalizedPayload, ["board_name"]);
    const sourceBoardName = readString(normalizedPayload, ["source_board_name"]);
    const groupName = readString(normalizedPayload, ["board_group_name"]);
    const error = readString(normalizedPayload, ["error"]);

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

export const activityCategoryForEvent = (eventType: string): ActivityCategory => {
  if (eventType.startsWith("task.execution_run.")) return "runs";
  if (eventType === "board.chat" || eventType === "board.command") return "chat";
  if (eventType.startsWith("task.")) return "tasks";
  if (eventType.startsWith("approval.")) return "approvals";
  if (eventType.startsWith("silo.runtime.")) return "runtime";
  if (eventType.startsWith("gateway.")) return "gateway";
  if (eventType.startsWith("board.")) return "boards";
  if (eventType.startsWith("agent.")) return "agents";
  return "all";
};
