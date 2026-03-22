"use client";

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

export type TaskDemandProfile = {
  label: string;
  tone: "success" | "warning" | "danger" | "neutral";
  guidance: string;
  reasons: DispatchReason[];
};

export const dispatchReasonClass = (tone: DispatchReason["tone"]): string => {
  if (tone === "success") return "bg-emerald-50 text-emerald-700";
  if (tone === "warning") return "bg-amber-50 text-amber-700";
  if (tone === "danger") return "bg-rose-50 text-rose-700";
  return "bg-slate-100 text-slate-700";
};

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
