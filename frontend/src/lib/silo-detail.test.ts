import { describe, expect, it } from "vitest";

import type { SiloDetail } from "@/lib/silos";
import {
  UNASSIGNED_GATEWAY,
  collectSiloWarnings,
  getAssignedGatewayRoleCount,
  getBlockedProvisionTargetCount,
  getLatestRuntimeAttemptedCount,
  getLatestRuntimeBlockedCount,
  getReadyProvisionTargetCount,
  hasActionableProvisionTargets,
  hasSiloConfigChanges,
} from "./silo-detail";
import { buildSiloDetailOpsViewModel } from "./silo-ops";

const buildDetail = (overrides: Partial<SiloDetail> = {}): SiloDetail => ({
  silo: {
    slug: "launch-crew",
    name: "Launch Crew",
    blueprint_slug: "default-four-agent",
    blueprint_version: "0.1.0",
    status: "draft",
    enable_symphony: false,
    enable_telemetry: true,
    role_count: 2,
  },
  desired_state: {
    slug: "launch-crew",
    name: "Launch Crew",
    blueprint_slug: "default-four-agent",
    blueprint_version: "0.1.0",
    enable_symphony: false,
    enable_telemetry: true,
    roles: [],
    shared_secret_bindings: [],
    warnings: ["Missing telemetry hub binding"],
  },
  roles: [
    {
      slug: "fox",
      display_name: "Fox",
      role_type: "pm",
      runtime_kind: "gateway",
      host_kind: "ec2",
      default_model: "anthropic/claude-sonnet-4-6",
      fallback_model: "openai-codex/gpt-5.3-codex",
      channel_name: "fox-tasks",
      gateway_id: "gateway-1",
      gateway_name: "Fox Gateway",
      workspace_root: "/workspace/fox",
      secret_bindings: [],
    },
    {
      slug: "symphony",
      display_name: "Symphony",
      role_type: "orchestrator",
      runtime_kind: "symphony",
      host_kind: "ec2",
      default_model: null,
      fallback_model: null,
      channel_name: null,
      gateway_id: null,
      gateway_name: null,
      workspace_root: null,
      secret_bindings: [],
    },
  ],
  provision_plan: {
    preview: { slug: "launch-crew" },
    targets: [
      {
        role_slug: "fox",
        runtime_kind: "gateway",
        gateway_name: "Fox Gateway",
        workspace_root: "/workspace/fox",
        supports_picoclaw_bundle_apply: true,
        warnings: [],
      },
      {
        role_slug: "symphony",
        runtime_kind: "symphony",
        gateway_name: null,
        workspace_root: null,
        supports_picoclaw_bundle_apply: false,
        warnings: ["Symphony runtime is not yet rendered into PicoClaw bundle apply payloads."],
      },
    ],
    warnings: ["One runtime target is blocked."],
  },
  latest_runtime_operation: {
    mode: "validate",
    created_at: "2026-03-20T00:00:00Z",
    warnings: ["Runtime validate saw one blocked role."],
    results: [
      {
        role_slug: "symphony",
        runtime_kind: "symphony",
        gateway_name: null,
        supports_picoclaw_bundle_apply: false,
        warnings: ["Blocked until Symphony bundle rendering exists."],
      },
    ],
  },
  workload_summary: {
    active_run_count: 1,
    queued_run_count: 0,
    running_run_count: 1,
    blocked_run_count: 0,
    failed_run_count: 0,
    last_activity_at: "2026-03-20T00:05:00Z",
    recent_runs: [
      {
        id: "run-1",
        board_id: "board-1",
        task_id: "task-1",
        task_title: "Validate launch plan",
        task_status: "in_progress",
        task_priority: "high",
        role_slug: "symphony",
        status: "running",
        summary: "Symphony worker session started.",
        completion_kind: null,
        failure_reason: null,
        block_reason: null,
        cancel_reason: null,
        stall_reason: null,
        created_at: "2026-03-20T00:00:00Z",
        updated_at: "2026-03-20T00:05:00Z",
        started_at: "2026-03-20T00:01:00Z",
        completed_at: null,
      },
    ],
  },
  ...overrides,
});

describe("silo-detail helpers", () => {
  it("counts assigned, ready, and blocked targets", () => {
    const detail = buildDetail();

    expect(getAssignedGatewayRoleCount(detail)).toBe(1);
    expect(getReadyProvisionTargetCount(detail)).toBe(1);
    expect(getBlockedProvisionTargetCount(detail)).toBe(1);
    expect(getLatestRuntimeAttemptedCount(detail)).toBe(0);
    expect(getLatestRuntimeBlockedCount(detail)).toBe(1);
    expect(hasActionableProvisionTargets(detail)).toBe(true);
  });

  it("collects unique warnings across desired state, plan, and runtime", () => {
    const detail = buildDetail({
      desired_state: {
        ...buildDetail().desired_state,
        warnings: ["Shared warning", "Missing telemetry hub binding"],
      },
      provision_plan: {
        ...buildDetail().provision_plan!,
        warnings: ["Shared warning", "One runtime target is blocked."],
      },
    });

    expect(collectSiloWarnings(detail)).toEqual([
      "Shared warning",
      "Missing telemetry hub binding",
      "One runtime target is blocked.",
      "Symphony runtime is not yet rendered into PicoClaw bundle apply payloads.",
      "Runtime validate saw one blocked role.",
      "Blocked until Symphony bundle rendering exists.",
    ]);
  });

  it("detects config changes from assignments and add-on drafts", () => {
    const detail = buildDetail();

    expect(
      hasSiloConfigChanges({
        detail,
        assignmentDrafts: {},
        enableSymphonyDraft: null,
        enableTelemetryDraft: null,
      }),
    ).toBe(false);

    expect(
      hasSiloConfigChanges({
        detail,
        assignmentDrafts: { fox: UNASSIGNED_GATEWAY },
        enableSymphonyDraft: null,
        enableTelemetryDraft: null,
      }),
    ).toBe(true);

    expect(
      hasSiloConfigChanges({
        detail,
        assignmentDrafts: {},
        enableSymphonyDraft: true,
        enableTelemetryDraft: null,
      }),
    ).toBe(true);
  });

  it("describes current silo workload in operator terms", () => {
    expect(buildSiloDetailOpsViewModel(buildDetail()).workloadGuidance).toBe(
      "This silo is actively carrying runtime work right now.",
    );

    expect(
      buildSiloDetailOpsViewModel(
        buildDetail({
          workload_summary: {
            ...buildDetail().workload_summary!,
            active_run_count: 0,
            running_run_count: 0,
            blocked_run_count: 1,
          },
        }),
      ).workloadGuidance,
    ).toBe(
      "Blocked runs need operator attention before this silo can be trusted with more work.",
    );
  });

  it("reflects workload pressure in health summary when runtime is otherwise ready", () => {
    const summary = buildSiloDetailOpsViewModel(
      buildDetail({
        silo: {
          ...buildDetail().silo,
          status: "active",
          active_run_count: 2,
        },
        desired_state: { ...buildDetail().desired_state, warnings: [] },
        provision_plan: {
          ...buildDetail().provision_plan!,
          warnings: [],
          targets: [
            {
              role_slug: "fox",
              runtime_kind: "gateway",
              gateway_name: "Fox Gateway",
              workspace_root: "/workspace/fox",
              supports_picoclaw_bundle_apply: true,
              warnings: [],
            },
          ],
        },
        latest_runtime_operation: {
          mode: "apply",
          created_at: "2026-03-20T00:00:00Z",
          warnings: [],
          results: [
            {
              role_slug: "fox",
              runtime_kind: "gateway",
              gateway_name: "Fox Gateway",
              supports_picoclaw_bundle_apply: true,
              warnings: [],
            },
          ],
        },
        workload_summary: {
          ...buildDetail().workload_summary!,
          active_run_count: 2,
          running_run_count: 2,
        },
      }),
    ).healthSummary;

    expect(summary.label).toBe("Busy");
  });
});
