"use client";

import type { SiloSummary } from "@/lib/silos";

export type SiloHealthKey =
  | "healthy"
  | "busy"
  | "degraded"
  | "blocked"
  | "needs_setup";

export type SiloHealthModel = {
  key: SiloHealthKey;
  label: string;
  tone: "success" | "warning" | "danger" | "neutral";
  guidance: string;
};

export type SiloHealthSummary = {
  totalCount: number;
  healthyCount: number;
  busyCount: number;
  blockedCount: number;
  degradedCount: number;
  needsSetupCount: number;
};

export const buildSiloHealthModel = (silo: SiloSummary): SiloHealthModel => {
  if (silo.status !== "active") {
    return {
      key: "needs_setup",
      label: "Needs setup",
      tone: "warning",
      guidance:
        "This silo is not yet in a steady operating state. Finish setup before trusting it with more work.",
    };
  }

  if (silo.blocked_run_count > 0) {
    return {
      key: "blocked",
      label: "Blocked",
      tone: "danger",
      guidance:
        "Blocked runtime work is present. Clear the blockage before dispatching more load here.",
    };
  }

  if (silo.failed_run_count > 0) {
    return {
      key: "degraded",
      label: "Degraded",
      tone: "warning",
      guidance:
        "Recent runtime failures suggest this silo needs investigation before taking sensitive work.",
    };
  }

  if (silo.active_run_count > 0) {
    return {
      key: "busy",
      label: "Busy",
      tone: "neutral",
      guidance: "This silo is healthy, but it is already carrying active runtime work.",
    };
  }

  return {
    key: "healthy",
    label: "Healthy",
    tone: "success",
    guidance: "Healthy, idle, and ready to accept more runtime work.",
  };
};

export const summarizeSiloHealth = (silos: SiloSummary[]): SiloHealthSummary =>
  silos.reduce<SiloHealthSummary>(
    (acc, silo) => {
      acc.totalCount += 1;
      const health = buildSiloHealthModel(silo);
      if (health.key === "healthy") acc.healthyCount += 1;
      else if (health.key === "busy") acc.busyCount += 1;
      else if (health.key === "blocked") acc.blockedCount += 1;
      else if (health.key === "degraded") acc.degradedCount += 1;
      else acc.needsSetupCount += 1;
      return acc;
    },
    {
      totalCount: 0,
      healthyCount: 0,
      busyCount: 0,
      blockedCount: 0,
      degradedCount: 0,
      needsSetupCount: 0,
    },
  );
