"use client";

import type { BoardRead } from "@/api/generated/model/boardRead";
import { customFetch } from "@/api/mutator";

export type SiloSpawnRequestScope = "organization" | "board" | "silo";
export type SiloSpawnRequestStatus =
  | "requested"
  | "planned"
  | "spawning"
  | "running"
  | "materialized"
  | "failed"
  | "cancelled";
export type SiloSpawnRequestPriority = "low" | "normal" | "high" | "urgent";

export type SiloSpawnRequest = {
  id: string;
  organization_id: string;
  requested_by_user_id: string | null;
  source_task_id: string | null;
  source_task_title: string | null;
  materialized_silo_id: string | null;
  materialized_silo_slug: string | null;
  materialized_at: string | null;
  slug: string;
  display_name: string;
  silo_kind: string;
  scope: SiloSpawnRequestScope;
  priority: SiloSpawnRequestPriority;
  board_id: string | null;
  parent_silo_id: string | null;
  desired_role: string | null;
  runtime_preference: string | null;
  status: SiloSpawnRequestStatus;
  summary: string | null;
  desired_state: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export async function fetchSiloSpawnRequests(): Promise<SiloSpawnRequest[]> {
  const response = await customFetch<{ data: SiloSpawnRequest[] }>("/api/v1/silos/spawn-requests", {
    method: "GET",
  });
  return response.data;
}

export async function fetchSiloSpawnRequestsForBoard(
  boardId: string,
): Promise<SiloSpawnRequest[]> {
  const response = await customFetch<{ data: SiloSpawnRequest[] }>(
    `/api/v1/silos/spawn-requests?board_id=${encodeURIComponent(boardId)}`,
    {
      method: "GET",
    },
  );
  return response.data;
}

export async function createSiloSpawnRequest(payload: {
  display_name: string;
  silo_kind: string;
  scope: SiloSpawnRequestScope;
  priority?: SiloSpawnRequestPriority;
  board_id?: string | null;
  parent_silo_id?: string | null;
  source_task_id?: string | null;
  desired_role?: string | null;
  source_task_title?: string | null;
  runtime_preference?: string | null;
  summary?: string | null;
}): Promise<SiloSpawnRequest> {
  const response = await customFetch<{ data: SiloSpawnRequest }>(
    "/api/v1/silos/spawn-requests",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
  return response.data;
}

export async function fetchSiloSpawnRequest(requestId: string): Promise<SiloSpawnRequest> {
  const response = await customFetch<{ data: SiloSpawnRequest }>(
    `/api/v1/silos/spawn-requests/${requestId}`,
    {
      method: "GET",
    },
  );
  return response.data;
}

export async function updateSiloSpawnRequest(
  requestId: string,
  payload: {
    status?: SiloSpawnRequestStatus;
    priority?: SiloSpawnRequestPriority;
    source_task_title?: string | null;
    summary?: string | null;
    desired_state?: Record<string, unknown> | null;
  },
): Promise<SiloSpawnRequest> {
  const response = await customFetch<{ data: SiloSpawnRequest }>(
    `/api/v1/silos/spawn-requests/${requestId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
  return response.data;
}

export async function fetchBoardOptions(): Promise<BoardRead[]> {
  const response = await customFetch<{ data: { items: BoardRead[] } }>("/api/v1/boards?limit=200&offset=0", {
    method: "GET",
  });
  return response.data.items;
}
