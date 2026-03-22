"use client";

import type { SiloSummary } from "@/lib/silos";
import {
  type DispatchReason,
  type TaskDemandInput,
} from "@/lib/silo-ops/demand";
import {
  buildSiloHealthModel,
  type SiloHealthModel,
} from "@/lib/silo-ops/health";

export type SiloDispatchCandidate = {
  silo: SiloSummary;
  health: SiloHealthModel;
  readinessLabel: string;
  tone: "success" | "warning" | "danger" | "neutral";
  guidance: string;
  reasons: DispatchReason[];
  score: number;
};

export const buildSiloDispatchCandidate = (
  silo: SiloSummary,
  task: TaskDemandInput,
): SiloDispatchCandidate => {
  const health = buildSiloHealthModel(silo);
  const hasPressure = health.key === "blocked" || health.key === "degraded";
  const isBusy = health.key === "busy";
  const taskNeedsUrgentAttention = Boolean(
    task &&
      ((task.approvals_pending_count ?? 0) > 0 ||
        task.is_blocked ||
        task.priority === "high"),
  );
  const reasons: DispatchReason[] = [];

  if (silo.enable_symphony) {
    reasons.push({ label: "Symphony enabled", tone: "success" });
  }
  if (silo.status === "active") {
    reasons.push({ label: "Healthy runtime", tone: "success" });
  }
  if (!isBusy) {
    reasons.push({ label: "Idle capacity", tone: "success" });
  }
  if (task?.priority === "high") {
    reasons.push({ label: "Fits urgent work", tone: "success" });
  }
  if ((task?.approvals_pending_count ?? 0) > 0) {
    reasons.push({ label: "Fast approval follow-up", tone: "success" });
  }
  if (task?.status === "in_progress" || task?.status === "review") {
    reasons.push({ label: "Good for active follow-up", tone: "neutral" });
  }

  if (hasPressure) {
    return {
      silo,
      health,
      readinessLabel: "Needs attention",
      tone: "danger",
      guidance: health.guidance,
      reasons: [
        {
          label: health.key === "blocked" ? "Blocked runs present" : "Recent failures present",
          tone: health.key === "blocked" ? "danger" : "warning",
        },
        ...(taskNeedsUrgentAttention
          ? [{ label: "Poor fit for urgent follow-up", tone: "warning" } satisfies DispatchReason]
          : []),
      ],
      score: 300 + silo.blocked_run_count * 10 + silo.failed_run_count * 10,
    };
  }

  if (silo.status !== "active") {
    return {
      silo,
      health,
      readinessLabel: silo.status === "provisioning" ? "Applying" : "Needs setup",
      tone: "warning",
      guidance: health.guidance,
      reasons: [
        {
          label: silo.status === "provisioning" ? "Runtime still applying" : "Needs setup first",
          tone: "warning",
        },
        ...(taskNeedsUrgentAttention
          ? [{ label: "Weak fit for urgent work", tone: "warning" } satisfies DispatchReason]
          : []),
      ],
      score: 200,
    };
  }

  if (isBusy) {
    return {
      silo,
      health,
      readinessLabel: "Available but busy",
      tone: taskNeedsUrgentAttention ? "warning" : "neutral",
      guidance: taskNeedsUrgentAttention
        ? "This silo can run work, but it already has active load and may not be ideal for urgent follow-up."
        : "This silo is healthy but already carrying active work.",
      reasons: [
        { label: "Healthy runtime", tone: "success" },
        { label: `Active load ${silo.active_run_count}`, tone: "warning" },
        ...(taskNeedsUrgentAttention
          ? [{ label: "Busy for urgent demand", tone: "warning" } satisfies DispatchReason]
          : [{ label: "Still available", tone: "neutral" } satisfies DispatchReason]),
      ],
      score: 100 + silo.active_run_count * 10,
    };
  }

  return {
    silo,
    health,
    readinessLabel: "Ready now",
    tone: "success",
    guidance: "Healthy, idle, and ready to accept a new runtime run.",
    reasons,
    score: 0,
  };
};

export const buildSiloOverviewPosture = (silo: SiloSummary): SiloDispatchCandidate =>
  buildSiloDispatchCandidate(silo, null);
