"use client";

import type { SiloDetail, SiloSummary } from "@/lib/silos";
import type { TaskExecutionRunSnapshot } from "@/lib/runtime-runs";
import {
  buildSiloOverviewPosture,
  buildSiloDispatchCandidate,
  type SiloDispatchCandidate,
} from "@/lib/silo-ops/dispatch";
import {
  buildTaskDemandProfile,
  type TaskDemandInput,
  type TaskDemandProfile,
} from "@/lib/silo-ops/demand";
import {
  buildSiloHealthModel,
  summarizeSiloHealth,
  type SiloHealthSummary,
} from "@/lib/silo-ops/health";
import {
  collectSiloWarnings,
  getAssignedGatewayRoleCount,
  getBlockedProvisionTargetCount,
  getGatewayRuntimeRoleCount,
  getLatestRuntimeBlockedCount,
  getReadyProvisionTargetCount,
} from "@/lib/silo-detail";

export type SiloHealthBadge = {
  text: string;
  tone: "online" | "offline" | "neutral";
};

export type DashboardSiloHealthViewModel = {
  summary: SiloHealthSummary;
  badge: SiloHealthBadge;
  primarySiloSlug: string | null;
};

export type SiloOverviewSummaryViewModel = {
  total: number;
  healthy: number;
  busy: number;
  blocked: number;
  degraded: number;
  needsSetup: number;
};

export type SiloDetailOpsViewModel = {
  healthSummary: {
    label: string;
    tone: "success" | "warning" | "danger" | "neutral";
    guidance: string;
  };
  runtimePosture: string;
  workloadGuidance: string;
};

export type TaskDispatchViewModel = {
  taskDemandProfile: TaskDemandProfile | null;
  candidates: SiloDispatchCandidate[];
  assignedSilo: {
    label: "Current silo" | "Last used silo";
    guidance: string;
    run: TaskExecutionRunSnapshot;
    candidate: SiloDispatchCandidate | null;
  } | null;
  selectedCandidate: SiloDispatchCandidate | null;
};

export const buildDashboardSiloHealthViewModel = (
  silos: SiloSummary[],
): DashboardSiloHealthViewModel => {
  const summary = summarizeSiloHealth(silos);
  const ranked = [...silos].sort((left, right) => {
    const leftPosture = buildSiloOverviewPosture(left);
    const rightPosture = buildSiloOverviewPosture(right);
    return rightPosture.score - leftPosture.score;
  });

  let badge: SiloHealthBadge;
  if (summary.totalCount === 0) {
    badge = { text: "No silos", tone: "neutral" };
  } else if (summary.blockedCount > 0) {
    badge = { text: "Blocked", tone: "offline" };
  } else if (summary.degradedCount > 0) {
    badge = { text: "Degraded", tone: "neutral" };
  } else if (summary.needsSetupCount > 0) {
    badge = { text: "Needs setup", tone: "neutral" };
  } else if (summary.busyCount > 0) {
    badge = { text: "Operational", tone: "neutral" };
  } else {
    badge = { text: "Healthy", tone: "online" };
  }

  return {
    summary,
    badge,
    primarySiloSlug: ranked[0]?.slug ?? null,
  };
};

export const buildSiloOverviewSummaryViewModel = (
  silos: SiloSummary[],
): SiloOverviewSummaryViewModel => {
  const summary = summarizeSiloHealth(silos);
  return {
    total: summary.totalCount,
    healthy: summary.healthyCount,
    busy: summary.busyCount,
    blocked: summary.blockedCount,
    degraded: summary.degradedCount,
    needsSetup: summary.needsSetupCount,
  };
};

export const buildSiloOverviewCards = (
  silos: SiloSummary[],
): SiloDispatchCandidate[] =>
  [...silos]
    .map((silo) => buildSiloOverviewPosture(silo))
    .sort((left, right) => left.silo.name.localeCompare(right.silo.name));

const buildSiloDetailHealthSummary = (
  detail: SiloDetail,
): SiloDetailOpsViewModel["healthSummary"] => {
  if (detail.operational_summary) {
    return {
      label: detail.operational_summary.health_label,
      tone: detail.operational_summary.health_tone,
      guidance: detail.operational_summary.health_guidance,
    };
  }
  const baseHealth = buildSiloHealthModel(detail.silo);
  const overviewPosture = buildSiloOverviewPosture(detail.silo);
  const warningCount = collectSiloWarnings(detail).length;
  const blockedTargets = getBlockedProvisionTargetCount(detail);
  const gatewayRoleCount = getGatewayRuntimeRoleCount(detail);
  const assignedGatewayRoles = getAssignedGatewayRoleCount(detail);

  if (blockedTargets > 0 || warningCount > 0) {
    return {
      label: blockedTargets > 0 ? "Blocked" : "Degraded",
      tone: blockedTargets > 0 ? "danger" : "warning",
      guidance:
        blockedTargets > 0
          ? "Resolve blocked runtime targets before trusting this silo with more work."
          : "Resolve runtime warnings before trusting this silo with more work.",
    };
  }

  if (gatewayRoleCount > 0 && assignedGatewayRoles < gatewayRoleCount) {
    return {
      label: "Needs setup",
      tone: "warning",
      guidance: "Assign gateway-backed roles before expecting healthy execution.",
    };
  }

  if (getReadyProvisionTargetCount(detail) > 0) {
    return {
      label: baseHealth.label,
      tone: baseHealth.tone,
      guidance:
        detail.latest_runtime_operation?.mode === "apply" &&
        getLatestRuntimeBlockedCount(detail) === 0
          ? "The latest runtime apply completed without blocked targets."
          : baseHealth.key === "needs_setup"
            ? "The silo is configured enough to validate or apply runtime."
            : baseHealth.guidance,
    };
  }

  return {
    label: overviewPosture.health.label,
    tone: overviewPosture.health.tone,
    guidance:
      overviewPosture.health.key === "needs_setup"
        ? "This silo exists, but it has not been driven into an operational state yet."
        : overviewPosture.health.guidance,
  };
};

const buildSiloRuntimePosture = (detail: SiloDetail): string => {
  if (detail.operational_summary?.runtime_posture) {
    return detail.operational_summary.runtime_posture;
  }
  const latestRuntime = detail.latest_runtime_operation;
  if (!latestRuntime) return "No runtime operation yet";
  if (latestRuntime.mode === "apply") {
    return getLatestRuntimeBlockedCount(detail) > 0
      ? "Latest apply needs follow-up"
      : "Latest apply completed";
  }
  return getLatestRuntimeBlockedCount(detail) > 0
    ? "Latest validate found blockers"
    : "Latest validate completed";
};

const buildSiloWorkloadGuidance = (detail: SiloDetail): string => {
  if (detail.operational_summary?.workload_guidance) {
    return detail.operational_summary.workload_guidance;
  }
  const workload = detail.workload_summary;
  if (!workload || workload.recent_runs.length === 0) {
    return "No runtime work has been dispatched to this silo yet.";
  }
  if (workload.blocked_run_count > 0) {
    return "Blocked runs need operator attention before this silo can be trusted with more work.";
  }
  if (workload.failed_run_count > 0) {
    return "Recent runtime failures should be investigated before scaling this silo further.";
  }
  if (workload.active_run_count > 0) {
    return "This silo is actively carrying runtime work right now.";
  }
  return "Recent runs completed; review the latest work before assigning more load.";
};

export const buildSiloDetailOpsViewModel = (
  detail: SiloDetail,
): SiloDetailOpsViewModel => ({
  healthSummary: buildSiloDetailHealthSummary(detail),
  runtimePosture: buildSiloRuntimePosture(detail),
  workloadGuidance: buildSiloWorkloadGuidance(detail),
});

const ACTIVE_ASSIGNMENT_STATUSES = new Set(["queued", "dispatching", "running", "blocked"]);

const parseRunTime = (value: string | null | undefined): number =>
  value ? Date.parse(value) || 0 : 0;

const pickAssignedRun = (
  runs: TaskExecutionRunSnapshot[],
): TaskExecutionRunSnapshot | null => {
  if (runs.length === 0) return null;

  const ranked = [...runs].sort((left, right) => {
    const leftActive = ACTIVE_ASSIGNMENT_STATUSES.has(left.status);
    const rightActive = ACTIVE_ASSIGNMENT_STATUSES.has(right.status);
    if (leftActive !== rightActive) return leftActive ? -1 : 1;
    return (
      parseRunTime(right.updated_at) - parseRunTime(left.updated_at) ||
      parseRunTime(right.created_at) - parseRunTime(left.created_at)
    );
  });

  return ranked[0] ?? null;
};

const buildAssignedSiloViewModel = (args: {
  silos: SiloSummary[];
  candidates: SiloDispatchCandidate[];
  task: TaskDemandInput;
  executionRuns: TaskExecutionRunSnapshot[];
}): TaskDispatchViewModel["assignedSilo"] => {
  const assignedRun = pickAssignedRun(args.executionRuns);
  if (!assignedRun) return null;

  const candidate =
    args.candidates.find((item) => item.silo.slug === assignedRun.silo_slug) ??
    (() => {
      const matchedSilo = args.silos.find((item) => item.slug === assignedRun.silo_slug);
      return matchedSilo ? buildSiloDispatchCandidate(matchedSilo, args.task) : null;
    })();

  const isCurrent = ACTIVE_ASSIGNMENT_STATUSES.has(assignedRun.status);
  const guidance = isCurrent
    ? "This task is already attached to this silo through an active run. Continue here unless you need to recover or rebalance."
    : assignedRun.status === "succeeded"
      ? "This silo handled the most recent run for this task. Reuse it to preserve continuity."
      : "This silo handled the most recent run for this task. Keep it for continuity or switch if recovery needs a different silo.";

  return {
    label: isCurrent ? "Current silo" : "Last used silo",
    guidance,
    run: assignedRun,
    candidate,
  };
};

export const buildTaskDispatchViewModel = (args: {
  silos: SiloSummary[];
  task: TaskDemandInput;
  executionRuns: TaskExecutionRunSnapshot[];
  selectedSiloSlug: string | null;
}): TaskDispatchViewModel => {
  const symphonyEnabledSilos = args.silos.filter((silo) => silo.enable_symphony);
  const candidates = [...symphonyEnabledSilos]
    .map((silo) => buildSiloDispatchCandidate(silo, args.task))
    .sort(
      (left, right) =>
        left.score - right.score || left.silo.name.localeCompare(right.silo.name),
    );
  const assignedSilo = buildAssignedSiloViewModel({
    silos: args.silos,
    candidates,
    task: args.task,
    executionRuns: args.executionRuns,
  });

  return {
    taskDemandProfile: buildTaskDemandProfile(args.task),
    candidates,
    assignedSilo,
    selectedCandidate:
      candidates.find((candidate) => candidate.silo.slug === args.selectedSiloSlug) ??
      assignedSilo?.candidate ??
      candidates[0] ??
      null,
  };
};
