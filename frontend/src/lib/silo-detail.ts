import type { SiloDetail } from "@/lib/silos";

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
