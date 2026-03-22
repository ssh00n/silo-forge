import type { SiloDetail } from "@/lib/silos";
import {
  buildSiloHealthModel,
  buildSiloOverviewPosture,
} from "@/lib/silo-dispatch";

export const UNASSIGNED_GATEWAY = "__unassigned__";

const normalizeWarning = (value: string) => value.trim();

export function getAssignedGatewayRoleCount(detail: SiloDetail): number {
  return detail.roles.filter(
    (role) => role.runtime_kind === "gateway" && Boolean(role.gateway_id),
  ).length;
}

export function getReadyProvisionTargetCount(detail: SiloDetail): number {
  return (
    detail.provision_plan?.targets.filter(
      (target) => target.supports_picoclaw_bundle_apply,
    ).length ?? 0
  );
}

export function getBlockedProvisionTargetCount(detail: SiloDetail): number {
  return (
    detail.provision_plan?.targets.filter(
      (target) => !target.supports_picoclaw_bundle_apply,
    ).length ?? 0
  );
}

export function getLatestRuntimeAttemptedCount(detail: SiloDetail): number {
  return (
    detail.latest_runtime_operation?.results.filter(
      (result) => result.supports_picoclaw_bundle_apply,
    ).length ?? 0
  );
}

export function getLatestRuntimeBlockedCount(detail: SiloDetail): number {
  return (
    detail.latest_runtime_operation?.results.filter(
      (result) => !result.supports_picoclaw_bundle_apply,
    ).length ?? 0
  );
}

export function collectSiloWarnings(detail: SiloDetail): string[] {
  const warnings = new Set<string>();

  detail.desired_state.warnings.forEach((warning) => {
    const normalized = normalizeWarning(warning);
    if (normalized) warnings.add(normalized);
  });
  detail.provision_plan?.warnings.forEach((warning) => {
    const normalized = normalizeWarning(warning);
    if (normalized) warnings.add(normalized);
  });
  detail.provision_plan?.targets.forEach((target) => {
    target.warnings.forEach((warning) => {
      const normalized = normalizeWarning(warning);
      if (normalized) warnings.add(normalized);
    });
  });
  detail.latest_runtime_operation?.warnings.forEach((warning) => {
    const normalized = normalizeWarning(warning);
    if (normalized) warnings.add(normalized);
  });
  detail.latest_runtime_operation?.results.forEach((result) => {
    result.warnings.forEach((warning) => {
      const normalized = normalizeWarning(warning);
      if (normalized) warnings.add(normalized);
    });
  });

  return [...warnings];
}

export function hasActionableProvisionTargets(detail: SiloDetail): boolean {
  return getReadyProvisionTargetCount(detail) > 0;
}

export function hasSiloConfigChanges(args: {
  detail: SiloDetail;
  assignmentDrafts: Record<string, string>;
  enableSymphonyDraft: boolean | null;
  enableTelemetryDraft: boolean | null;
}): boolean {
  const {
    detail,
    assignmentDrafts,
    enableSymphonyDraft,
    enableTelemetryDraft,
  } = args;

  const addOnChanged =
    (enableSymphonyDraft !== null &&
      enableSymphonyDraft !== detail.silo.enable_symphony) ||
    (enableTelemetryDraft !== null &&
      enableTelemetryDraft !== detail.silo.enable_telemetry);
  if (addOnChanged) return true;

  return detail.roles.some((role) => {
    if (role.runtime_kind !== "gateway") return false;
    const draftValue = assignmentDrafts[role.slug];
    if (draftValue === undefined) return false;
    const normalizedDraft =
      draftValue === UNASSIGNED_GATEWAY ? null : draftValue || null;
    return normalizedDraft !== (role.gateway_id ?? null);
  });
}

export function getGatewayRuntimeRoleCount(detail: SiloDetail): number {
  return detail.roles.filter((role) => role.runtime_kind === "gateway").length;
}

export function getSiloHealthSummary(detail: SiloDetail): {
  label: string;
  tone: "success" | "warning" | "danger" | "neutral";
  guidance: string;
} {
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
}

export function getSiloRuntimePosture(detail: SiloDetail): string {
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
}

export function getSiloWorkloadGuidance(detail: SiloDetail): string {
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
}
