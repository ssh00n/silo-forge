import { describe, expect, it } from "vitest";

import type { SiloSummary } from "@/lib/silos";
import {
  buildSiloHealthModel,
  buildSiloDispatchCandidate,
  buildSiloOverviewPosture,
  buildTaskDemandProfile,
  dispatchReasonClass,
  summarizeSiloHealth,
} from "./silo-dispatch";

const buildSilo = (overrides: Partial<SiloSummary> = {}): SiloSummary => ({
  slug: "launch-crew",
  name: "Launch Crew",
  blueprint_slug: "default-four-agent",
  blueprint_version: "0.1.0",
  status: "active",
  enable_symphony: true,
  enable_telemetry: true,
  role_count: 4,
  active_run_count: 0,
  blocked_run_count: 0,
  failed_run_count: 0,
  last_activity_at: null,
  ...overrides,
});

describe("silo-dispatch helpers", () => {
  it("prefers healthy idle silos for urgent work", () => {
    const candidate = buildSiloDispatchCandidate(buildSilo(), {
      status: "in_progress",
      priority: "high",
      approvals_pending_count: 0,
      is_blocked: false,
    });

    expect(candidate.readinessLabel).toBe("Ready now");
    expect(candidate.health.label).toBe("Healthy");
    expect(candidate.score).toBe(0);
    expect(candidate.reasons.some((reason) => reason.label === "Fits urgent work")).toBe(true);
  });

  it("marks pressured silos as needs attention", () => {
    const candidate = buildSiloDispatchCandidate(
      buildSilo({ blocked_run_count: 1, failed_run_count: 1 }),
      {
        status: "review",
        priority: "high",
        approvals_pending_count: 1,
        is_blocked: false,
      },
    );

    expect(candidate.readinessLabel).toBe("Needs attention");
    expect(candidate.tone).toBe("danger");
    expect(candidate.health.key).toBe("blocked");
    expect(candidate.reasons[0]?.label).toBe("Blocked runs present");
  });

  it("derives overview posture without task demand", () => {
    const posture = buildSiloOverviewPosture(buildSilo({ active_run_count: 2 }));

    expect(posture.readinessLabel).toBe("Available but busy");
    expect(posture.health.label).toBe("Busy");
    expect(posture.reasons.some((reason) => reason.label === "Active load 2")).toBe(true);
  });

  it("derives a degraded health model for recent failures", () => {
    const health = buildSiloHealthModel(buildSilo({ failed_run_count: 1 }));

    expect(health.key).toBe("degraded");
    expect(health.label).toBe("Degraded");
  });

  it("summarizes silo health using shared posture vocabulary", () => {
    const summary = summarizeSiloHealth([
      buildSilo(),
      buildSilo({ active_run_count: 1 }),
      buildSilo({ blocked_run_count: 1 }),
      buildSilo({ failed_run_count: 1 }),
      buildSilo({ status: "draft" }),
    ]);

    expect(summary.totalCount).toBe(5);
    expect(summary.healthyCount).toBe(1);
    expect(summary.busyCount).toBe(1);
    expect(summary.blockedCount).toBe(1);
    expect(summary.degradedCount).toBe(1);
    expect(summary.needsSetupCount).toBe(1);
  });

  it("builds approval pressure demand profile", () => {
    const profile = buildTaskDemandProfile({
      status: "review",
      priority: "medium",
      approvals_pending_count: 2,
      is_blocked: false,
    });

    expect(profile?.label).toBe("Approval pressure");
    expect(profile?.reasons[0]?.label).toBe("2 approvals pending");
  });

  it("returns tone-aware chip classes", () => {
    expect(dispatchReasonClass("success")).toContain("emerald");
    expect(dispatchReasonClass("warning")).toContain("amber");
    expect(dispatchReasonClass("danger")).toContain("rose");
    expect(dispatchReasonClass("neutral")).toContain("slate");
  });
});
