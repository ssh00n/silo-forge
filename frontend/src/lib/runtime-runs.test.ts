import { describe, expect, it } from "vitest";

import {
  extractRuntimeRunDetailsFromPayload,
  inferRuntimeRunStatusFromEvent,
  resolveRuntimeRunFeedContent,
  runtimeRunOperatorGuidance,
  runtimeRunOperatorState,
  runtimeRunFallbackSummary,
} from "@/lib/runtime-runs";

describe("runtime-runs helpers", () => {
  it("prefers payload status over message parsing", () => {
    expect(
      inferRuntimeRunStatusFromEvent(
        "task.execution_run.updated",
        "Symphony run abc is failed.",
        { status: "running" },
      ),
    ).toBe("running");
  });

  it("builds fallback summary for created events from payload", () => {
    expect(
      runtimeRunFallbackSummary("task.execution_run.created", {
        run_short_id: "abc12345",
        silo_slug: "demo-silo",
        role_slug: "symphony",
      }),
    ).toBe("Queued Symphony run `abc12345` for demo-silo/symphony.");
  });

  it("extracts structured detail rows from payload", () => {
    expect(
      extractRuntimeRunDetailsFromPayload({
        pull_request: 22,
        pr_url: "https://github.com/example/repo/pull/22",
        branch_name: "feature/task-backed-symphony",
        workspace_path: "/srv/symphony/workspaces/MC-22",
        external_run_id: "sym-22",
        issue_identifier: "MC-22",
        runner_kind: "codex",
        completion_kind: "normal",
        turn_count: 2,
        session_id: "session-22",
        last_event: "turn_completed",
        duration_ms: 65000,
        total_tokens: 320,
        error_message: "Runner exited with status 1",
      }),
    ).toEqual([
      { label: "PR #", value: "22" },
      { label: "PR", value: "https://github.com/example/repo/pull/22" },
      { label: "Branch", value: "feature/task-backed-symphony" },
      { label: "Workspace", value: "/srv/symphony/workspaces/MC-22" },
      { label: "External run", value: "sym-22" },
      { label: "Issue", value: "MC-22" },
      { label: "Runner", value: "codex" },
      { label: "Completion", value: "normal" },
      { label: "Turns", value: "2" },
      { label: "Session", value: "session-22" },
      { label: "Event", value: "turn_completed" },
      { label: "Duration", value: "1m 5s" },
      { label: "Tokens", value: "320" },
      { label: "Error", value: "Runner exited with status 1" },
    ]);
  });

  it("prefers payload summary and details before message parsing", () => {
    expect(
      resolveRuntimeRunFeedContent(
        "task.execution_run.report",
        "Symphony failed execution run `abc12345`.\nBranch: legacy-branch\nError: legacy error",
        {
          status: "succeeded",
          summary: "Opened PR with implementation updates.",
          pull_request: 44,
          total_tokens: 912,
          branch_name: "feature/payload-first",
        },
      ),
    ).toEqual({
      status: "succeeded",
      summary: "Opened PR with implementation updates.",
      details: [
        { label: "PR #", value: "44" },
        { label: "Branch", value: "feature/payload-first" },
        { label: "Tokens", value: "912" },
      ],
    });
  });

  it("falls back to message parsing when payload is absent", () => {
    expect(
      resolveRuntimeRunFeedContent(
        "task.execution_run.report",
        "Symphony failed execution run `abc12345`.\nPR #22\nTokens: 320",
        null,
      ),
    ).toEqual({
      status: "failed",
      summary: "Symphony failed execution run `abc12345`.",
      details: [
        { label: "PR #", value: "22" },
        { label: "Tokens", value: "320" },
      ],
    });
  });

  it("builds operator guidance for blocked approval-style runs", () => {
    expect(
      runtimeRunOperatorGuidance({
        id: "run-1",
        board_id: "board-1",
        task_id: "task-1",
        status: "blocked",
        created_at: "2026-03-22T00:00:00Z",
        updated_at: "2026-03-22T00:01:00Z",
        block_reason: "Waiting for lead approval before continuing.",
      }),
    ).toEqual({
      tone: "warning",
      title: "Resolve the block",
      detail: "Waiting for lead approval before continuing.",
    });
  });

  it("builds operator guidance for failed runs from error context", () => {
    expect(
      runtimeRunOperatorGuidance({
        id: "run-2",
        board_id: "board-1",
        task_id: "task-1",
        status: "failed",
        created_at: "2026-03-22T00:00:00Z",
        updated_at: "2026-03-22T00:01:00Z",
        error_message: "Codex runner exited with status 1",
      }),
    ).toEqual({
      tone: "danger",
      title: "Investigate failure",
      detail: "Codex runner exited with status 1",
    });
  });

  it("classifies stale running runs as stalled", () => {
    expect(
      runtimeRunOperatorState({
        id: "run-3",
        board_id: "board-1",
        task_id: "task-1",
        status: "running",
        created_at: "2026-03-22T00:00:00Z",
        updated_at: "2026-03-21T00:00:00Z",
      }),
    ).toEqual({
      tone: "warning",
      label: "stalled",
    });
  });

  it("classifies blocked runs from explicit block reasons", () => {
    expect(
      runtimeRunOperatorState({
        id: "run-4",
        board_id: "board-1",
        task_id: "task-1",
        status: "blocked",
        created_at: "2026-03-22T00:00:00Z",
        updated_at: "2026-03-22T00:01:00Z",
        block_reason: "approval gate pending",
      }),
    ).toEqual({
      tone: "warning",
      label: "approval blocked",
    });
  });
});
