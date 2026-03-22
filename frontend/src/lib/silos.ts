"use client";

import { customFetch } from "@/api/mutator";

export type SiloSummary = {
  slug: string;
  name: string;
  blueprint_slug: string;
  blueprint_version: string;
  status: "draft" | "provisioning" | "active" | "paused" | "archived";
  enable_symphony: boolean;
  enable_telemetry: boolean;
  role_count: number;
  active_run_count: number;
  blocked_run_count: number;
  failed_run_count: number;
  last_activity_at: string | null;
};

export type SiloSecretBinding = {
  name: string;
  vault_path: string;
  vault_key: string;
  env_var: string;
  required: boolean;
};

export type SiloRole = {
  slug: string;
  display_name: string;
  role_type: string;
  runtime_kind: "gateway" | "symphony";
  host_kind: string;
  default_model: string | null;
  fallback_model: string | null;
  channel_name: string | null;
  gateway_id: string | null;
  gateway_name: string | null;
  workspace_root: string | null;
  secret_bindings: SiloSecretBinding[];
};

export type RuntimeOperationResult = {
  role_slug: string;
  runtime_kind: "gateway" | "symphony";
  gateway_name: string | null;
  supports_picoclaw_bundle_apply: boolean;
  validated?: { valid: boolean; restart_required: boolean } | null;
  applied?: { applied: boolean; restart_required: boolean } | null;
  warnings: string[];
};

export type SiloWorkloadRun = {
  id: string;
  board_id: string;
  task_id: string;
  task_title: string;
  task_status: string | null;
  task_priority: string | null;
  role_slug: string;
  status:
    | "queued"
    | "dispatching"
    | "running"
    | "succeeded"
    | "failed"
    | "cancelled"
    | "blocked";
  summary: string | null;
  completion_kind: string | null;
  failure_reason: string | null;
  block_reason: string | null;
  cancel_reason: string | null;
  stall_reason: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type SiloDetail = {
  silo: SiloSummary;
  operational_summary: {
    health_label: string;
    health_tone: "success" | "warning" | "danger" | "neutral";
    health_guidance: string;
    runtime_posture: string;
    workload_guidance: string;
  } | null;
  desired_state: {
    slug: string;
    name: string;
    blueprint_slug: string;
    blueprint_version: string;
    enable_symphony: boolean;
    enable_telemetry: boolean;
    roles: SiloRole[];
    shared_secret_bindings: SiloSecretBinding[];
    warnings: string[];
  };
  roles: SiloRole[];
  provision_plan: {
    preview: { slug: string };
    targets: Array<{
      role_slug: string;
      runtime_kind: "gateway" | "symphony";
      gateway_name: string | null;
      workspace_root: string | null;
      supports_picoclaw_bundle_apply: boolean;
      warnings: string[];
    }>;
    warnings: string[];
  } | null;
  latest_runtime_operation: {
    mode: "validate" | "apply";
    created_at: string;
    results: RuntimeOperationResult[];
    warnings: string[];
  } | null;
  workload_summary: {
    active_run_count: number;
    queued_run_count: number;
    running_run_count: number;
    blocked_run_count: number;
    failed_run_count: number;
    recent_runs: SiloWorkloadRun[];
    last_activity_at: string | null;
  } | null;
};

export type SiloRuntimeResponse = {
  silo: SiloSummary;
  mode: "validate" | "apply";
  results: RuntimeOperationResult[];
  warnings: string[];
};

export type SiloBlueprint = {
  slug: string;
  version: string;
  display_name: string;
  description: string;
  supports_symphony: boolean;
  supports_telemetry: boolean;
  roles: Array<{
    slug: string;
    display_name: string;
    role_type: string;
    runtime_kind: "gateway" | "symphony";
  }>;
};

export async function fetchSilos(): Promise<SiloSummary[]> {
  const response = await customFetch<{ data: SiloSummary[] }>("/api/v1/silos", {
    method: "GET",
  });
  return response.data;
}

export async function fetchSiloBlueprints(): Promise<SiloBlueprint[]> {
  const response = await customFetch<{ data: SiloBlueprint[] }>(
    "/api/v1/silo-blueprints",
    { method: "GET" },
  );
  return response.data;
}

export async function createSilo(payload: {
  name: string;
  blueprint_slug: string;
  enable_symphony: boolean;
  enable_telemetry: boolean;
  gateway_assignments: Array<{
    role_slug: string;
    gateway_id: string | null;
    workspace_root?: string | null;
  }>;
}): Promise<SiloSummary> {
  const response = await customFetch<{ data: SiloSummary }>("/api/v1/silos", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return response.data;
}

export async function updateSilo(
  slug: string,
  payload: {
    enable_symphony?: boolean;
    enable_telemetry?: boolean;
    gateway_assignments: Array<{
      role_slug: string;
      gateway_id: string | null;
      workspace_root?: string | null;
    }>;
  },
): Promise<SiloDetail> {
  const response = await customFetch<{ data: SiloDetail }>(`/api/v1/silos/${slug}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return response.data;
}

export async function fetchSiloDetail(slug: string): Promise<SiloDetail> {
  const response = await customFetch<{ data: SiloDetail }>(
    `/api/v1/silos/${slug}/detail`,
    { method: "GET" },
  );
  return response.data;
}

export async function runSiloRuntime(
  slug: string,
  mode: "validate" | "apply",
): Promise<SiloRuntimeResponse> {
  const response = await customFetch<{ data: SiloRuntimeResponse }>(
    `/api/v1/silos/${slug}/runtime/${mode}`,
    { method: "POST" },
  );
  return response.data;
}
