import { describe, expect, it } from "vitest";

import {
  activityCategoryForEvent,
  resolveActivityFeedContent,
} from "@/lib/activity-events";

describe("activity-events helpers", () => {
  it("builds task status summaries and details from payload", () => {
    expect(
      resolveActivityFeedContent("task.status_changed", "legacy message", {
        task_title: "Ship runtime payloads",
        status: "review",
        previous_status: "in_progress",
        reason: "execution_run_succeeded",
      }),
    ).toEqual({
      summary: "Task moved to review: Ship runtime payloads.",
      details: [
        { label: "Status", value: "review" },
        { label: "Previous", value: "in_progress" },
        { label: "Reason", value: "execution_run_succeeded" },
      ],
      runtimeStatus: null,
    });
  });

  it("builds approval details from payload", () => {
    expect(
      resolveActivityFeedContent("approval.lead_notify_failed", "Lead notify failed", {
        action_type: "deploy",
        approval_status: "rejected",
        notification_status: "failed",
        error: "gateway unavailable",
      }),
    ).toEqual({
      summary: "Lead notify failed",
      details: [
        { label: "Decision", value: "rejected" },
        { label: "Action", value: "deploy" },
        { label: "Notify", value: "failed" },
        { label: "Error", value: "gateway unavailable" },
      ],
      runtimeStatus: null,
    });
  });

  it("builds task notification details from payload", () => {
    expect(
      resolveActivityFeedContent("task.assignee_notified", "Agent notified for assignment", {
        task_title: "Ship dashboard feed cleanup",
        target_agent_name: "Bunny",
        notification_kind: "assignment",
        notification_status: "sent",
        status: "in_progress",
      }),
    ).toEqual({
      summary: "Agent notified for assignment",
      details: [
        { label: "Task", value: "Ship dashboard feed cleanup" },
        { label: "Agent", value: "Bunny" },
        { label: "Kind", value: "assignment" },
        { label: "Notify", value: "sent" },
        { label: "Status", value: "in_progress" },
      ],
      runtimeStatus: null,
    });
  });

  it("builds generic board notification details from payload", () => {
    expect(
      resolveActivityFeedContent(
        "board.group.join.notify_failed",
        "Board-group join notify failed",
        {
          notification_kind: "board_group_join",
          notification_status: "failed",
          target_agent_name: "Fox",
          board_name: "Ops Board",
          source_board_name: "Core Board",
          board_group_name: "Delivery",
          error: "gateway unavailable",
        },
      ),
    ).toEqual({
      summary: "Board-group join notify failed",
      details: [
        { label: "Kind", value: "board_group_join" },
        { label: "Notify", value: "failed" },
        { label: "Agent", value: "Fox" },
        { label: "Board", value: "Ops Board" },
        { label: "Source", value: "Core Board" },
        { label: "Group", value: "Delivery" },
        { label: "Error", value: "gateway unavailable" },
      ],
      runtimeStatus: null,
    });
  });

  it("builds agent lifecycle details from payload", () => {
    expect(
      resolveActivityFeedContent("agent.provision.failed", "Provision failed", {
        agent_name: "Fox",
        action: "provision",
        delivery_status: "failed",
        gateway_name: "Fox Host",
        error: "gateway unavailable",
      }),
    ).toEqual({
      summary: "Provision failed",
      details: [
        { label: "Agent", value: "Fox" },
        { label: "Action", value: "provision" },
        { label: "Delivery", value: "failed" },
        { label: "Gateway", value: "Fox Host" },
        { label: "Error", value: "gateway unavailable" },
      ],
      runtimeStatus: null,
    });
  });

  it("builds gateway summaries from structured payload when message is absent", () => {
    expect(
      resolveActivityFeedContent("gateway.main.lead_message.sent", "", {
        notification_kind: "gateway_lead_message",
        notification_status: "sent",
        gateway_name: "Demo Gateway",
        action: "lead_message",
        target_kind: "lead",
      }),
    ).toEqual({
      summary: "lead_message sent.",
      details: [
        { label: "Kind", value: "gateway_lead_message" },
        { label: "Notify", value: "sent" },
        { label: "Gateway", value: "Demo Gateway" },
        { label: "Action", value: "lead_message" },
        { label: "Target", value: "lead" },
      ],
      runtimeStatus: null,
    });
  });

  it("builds board summaries from structured payload when message is absent", () => {
    expect(
      resolveActivityFeedContent("board.group.join.notified", "", {
        notification_kind: "board_group_join",
        notification_status: "sent",
        board_name: "Ops Board",
        target_agent_name: "Fox",
      }),
    ).toEqual({
      summary: "board group join on Ops Board.",
      details: [
        { label: "Kind", value: "board_group_join" },
        { label: "Notify", value: "sent" },
        { label: "Agent", value: "Fox" },
        { label: "Board", value: "Ops Board" },
      ],
      runtimeStatus: null,
    });
  });

  it("builds silo runtime details from payload", () => {
    expect(
      resolveActivityFeedContent("silo.runtime.validate", "Validated runtime bundle plan", {
        silo_name: "Demo Silo",
        mode: "validate",
        result_count: "4",
        warning_count: "1",
        restart_required: "yes",
        gateway_names: "Fox Host",
        roles: "fox, bunny, owl, otter",
      }),
    ).toEqual({
      summary: "Validated runtime bundle plan",
      details: [
        { label: "Silo", value: "Demo Silo" },
        { label: "Mode", value: "validate" },
        { label: "Results", value: "4" },
        { label: "Warnings", value: "1" },
        { label: "Restart", value: "yes" },
        { label: "Gateways", value: "Fox Host" },
        { label: "Roles", value: "fox, bunny, owl, otter" },
      ],
      runtimeStatus: null,
    });
  });

  it("builds queue worker telemetry details from payload", () => {
    expect(
      resolveActivityFeedContent("queue.worker.failed", "Queue worker failed task_execution_dispatch", {
        queue_name: "default",
        status: "failed",
        task_type: "task_execution_dispatch",
        attempt: 2,
        retry_delay_seconds: 5.5,
        error: "boom",
      }),
    ).toEqual({
      summary: "Queue worker failed task_execution_dispatch",
      details: [
        { label: "Queue", value: "default" },
        { label: "Status", value: "failed" },
        { label: "Task type", value: "task_execution_dispatch" },
        { label: "Attempt", value: "2" },
        { label: "Retry", value: "5.5s" },
        { label: "Error", value: "boom" },
      ],
      runtimeStatus: null,
    });
  });

  it("builds webhook dispatch telemetry details from payload", () => {
    expect(
      resolveActivityFeedContent("webhook.dispatch.requeued", "", {
        status: "requeued",
        payload_id: "payload-123",
        webhook_id: "webhook-456",
        attempt: 1,
        retry_delay_seconds: 3,
      }),
    ).toEqual({
      summary: "Webhook dispatch requeued.",
      details: [
        { label: "Status", value: "requeued" },
        { label: "Payload", value: "payload-123" },
        { label: "Webhook", value: "webhook-456" },
        { label: "Attempt", value: "1" },
        { label: "Retry", value: "3s" },
      ],
      runtimeStatus: null,
    });
  });

  it("classifies activity categories for filters", () => {
    expect(activityCategoryForEvent("task.execution_run.report")).toBe("runs");
    expect(activityCategoryForEvent("silo.runtime.validate")).toBe("runtime");
    expect(activityCategoryForEvent("queue.worker.failed")).toBe("runtime");
    expect(activityCategoryForEvent("task.status_changed")).toBe("tasks");
    expect(activityCategoryForEvent("approval.created")).toBe("approvals");
    expect(activityCategoryForEvent("board.lead_notified")).toBe("boards");
    expect(activityCategoryForEvent("agent.provision.failed")).toBe("agents");
    expect(activityCategoryForEvent("webhook.dispatch.success")).toBe("gateway");
    expect(activityCategoryForEvent("gateway.main.lead_message.sent")).toBe("gateway");
    expect(activityCategoryForEvent("board.chat")).toBe("chat");
  });
});
