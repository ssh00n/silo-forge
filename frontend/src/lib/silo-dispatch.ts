"use client";

import type { SiloSummary } from "@/lib/silos";

export type DispatchReason = {
  label: string;
  tone: "success" | "warning" | "danger" | "neutral";
};

export type TaskDemandInput = {
  status: string;
  priority: string;
  is_blocked?: boolean;
  approvals_pending_count?: number;
} | null;

export type SiloDispatchCandidate = {
  silo: SiloSummary;
  readinessLabel: string;
  tone: "success" | "warning" | "danger" | "neutral";
  guidance: string;
  reasons: DispatchReason[];
  score: number;
};

export type TaskDemandProfile = {
  label: string;
  tone: "success" | "warning" | "danger" | "neutral";
  guidance: string;
  reasons: DispatchReason[];
};

export type SiloHealthSummary = {
  totalCount: number;
  readyCount: number;
  busyCount: number;
  needsAttentionCount: number;
  needsSetupCount: number;
};

export const dispatchReasonClass = (tone: DispatchReason["tone"]): string => {
  if (tone === "success") return "bg-emerald-50 text-emerald-700";
  if (tone === "warning") return "bg-amber-50 text-amber-700";
  if (tone === "danger") return "bg-rose-50 text-rose-700";
  return "bg-slate-100 text-slate-700";
};

export const buildSiloDispatchCandidate = (
  silo: SiloSummary,
  task: TaskDemandInput,
): SiloDispatchCandidate => {
  const hasPressure = silo.blocked_run_count > 0 || silo.failed_run_count > 0;
  const isBusy = silo.active_run_count > 0;
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
      readinessLabel: "Needs attention",
      tone: "danger",
      guidance:
        "Recent blocked or failed runtime work should be resolved before dispatching more work here.",
      reasons: [
        { label: "Blocked or failed runs present", tone: "danger" },
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
      readinessLabel: silo.status === "provisioning" ? "Applying" : "Needs setup",
      tone: "warning",
      guidance:
        "This silo is not yet in a steady operating state. Verify readiness before dispatching work.",
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
    readinessLabel: "Ready now",
    tone: "success",
    guidance: "Healthy, idle, and ready to accept a new runtime run.",
    reasons,
    score: 0,
  };
};

export const buildSiloOverviewPosture = (silo: SiloSummary): SiloDispatchCandidate =>
  buildSiloDispatchCandidate(silo, null);

export const summarizeSiloHealth = (silos: SiloSummary[]): SiloHealthSummary =>
  silos.reduce<SiloHealthSummary>(
    (acc, silo) => {
      acc.totalCount += 1;
      const posture = buildSiloOverviewPosture(silo);
      if (posture.readinessLabel === "Ready now") acc.readyCount += 1;
      else if (posture.readinessLabel === "Available but busy") acc.busyCount += 1;
      else if (posture.readinessLabel === "Needs attention") acc.needsAttentionCount += 1;
      else acc.needsSetupCount += 1;
      return acc;
    },
    {
      totalCount: 0,
      readyCount: 0,
      busyCount: 0,
      needsAttentionCount: 0,
      needsSetupCount: 0,
    },
  );

export const buildTaskDemandProfile = (
  task: TaskDemandInput,
): TaskDemandProfile | null => {
  if (!task) return null;
  if ((task.approvals_pending_count ?? 0) > 0) {
    return {
      label: "Approval pressure",
      tone: "warning",
      guidance:
        "This task is waiting on an approval decision. Prefer a healthy silo that can resume quickly once the gate clears.",
      reasons: [
        { label: `${task.approvals_pending_count} approvals pending`, tone: "warning" },
        { label: "Needs quick operator follow-up", tone: "warning" },
      ],
    };
  }
  if (task.is_blocked) {
    return {
      label: "Blocked dependencies",
      tone: "warning",
      guidance:
        "The task has unresolved dependencies. Avoid assigning a busy or degraded silo until the block is cleared.",
      reasons: [
        { label: "Dependency blocked", tone: "warning" },
        { label: "Avoid degraded silos", tone: "warning" },
      ],
    };
  }
  if (task.priority === "high") {
    return {
      label: "High-priority workload",
      tone: "danger",
      guidance:
        "Use the healthiest, least-busy silo available so the task can move immediately.",
      reasons: [
        { label: "Priority high", tone: "danger" },
        { label: "Prefer idle healthy silo", tone: "warning" },
      ],
    };
  }
  if (task.status === "in_progress" || task.status === "review") {
    return {
      label: "Active follow-up",
      tone: "neutral",
      guidance:
        "This task is already in motion. Favor a ready silo that can continue work without more setup.",
      reasons: [
        { label: `Task ${task.status}`, tone: "neutral" },
        { label: "Favor continuity", tone: "neutral" },
      ],
    };
  }
  return {
    label: "Standard demand",
    tone: "success",
    guidance:
      "Any ready silo can take this work. Prefer an idle silo if one is available.",
    reasons: [
      { label: `Task ${task.status}`, tone: "neutral" },
      { label: "Standard load", tone: "success" },
    ],
  };
};
