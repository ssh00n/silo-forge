"use client";

export const dynamic = "force-dynamic";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/clerk";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import {
  createSiloSpawnRequest,
  fetchBoardOptions,
  fetchSiloSpawnRequests,
  type SiloSpawnRequestPriority,
  type SiloSpawnRequestScope,
  updateSiloSpawnRequest,
} from "@/lib/silo-spawn-requests";

const KIND_OPTIONS = [
  { value: "agent", label: "Single-agent silo" },
  { value: "team", label: "Multi-agent silo" },
];
const PRIORITY_OPTIONS: Array<{ value: SiloSpawnRequestPriority; label: string }> = [
  { value: "urgent", label: "Urgent" },
  { value: "high", label: "High" },
  { value: "normal", label: "Normal" },
  { value: "low", label: "Low" },
];

const priorityRank: Record<SiloSpawnRequestPriority, number> = {
  urgent: 0,
  high: 1,
  normal: 2,
  low: 3,
};

const priorityPillClass = (priority: SiloSpawnRequestPriority): string => {
  if (priority === "urgent") return "bg-rose-50 text-rose-700 border border-rose-200";
  if (priority === "high") return "bg-amber-50 text-amber-700 border border-amber-200";
  if (priority === "low") return "bg-slate-100 text-slate-600 border border-slate-200";
  return "bg-blue-50 text-blue-700 border border-blue-200";
};

export default function SiloRequestsPage() {
  const searchParams = useSearchParams();
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);
  const queryClient = useQueryClient();
  const prefilledBoardId = searchParams.get("board_id") ?? "";
  const prefilledTaskId = searchParams.get("task_id") ?? "";
  const prefilledTaskTitle = searchParams.get("task_title") ?? "";
  const prefilledPriority = searchParams.get("priority");
  const initialPriority =
    prefilledPriority === "urgent" ||
    prefilledPriority === "high" ||
    prefilledPriority === "low"
      ? prefilledPriority
      : "normal";
  const [displayName, setDisplayName] = useState(
    prefilledTaskTitle ? `${prefilledTaskTitle} silo` : "",
  );
  const [siloKind, setSiloKind] = useState("agent");
  const [scope, setScope] = useState<Extract<SiloSpawnRequestScope, "organization" | "board">>(
    prefilledBoardId ? "board" : "organization",
  );
  const [priority, setPriority] = useState<SiloSpawnRequestPriority>(initialPriority);
  const [boardId, setBoardId] = useState(prefilledBoardId);
  const [sourceTaskId, setSourceTaskId] = useState(prefilledTaskId);
  const [sourceTaskTitle, setSourceTaskTitle] = useState(prefilledTaskTitle);
  const [desiredRole, setDesiredRole] = useState("");
  const [runtimePreference, setRuntimePreference] = useState("");
  const [summary, setSummary] = useState(
    prefilledTaskTitle ? `Support task demand for ${prefilledTaskTitle}.` : "",
  );
  const [error, setError] = useState<string | null>(null);
  const [updatingRequestId, setUpdatingRequestId] = useState<string | null>(null);

  const requestsQuery = useQuery({
    queryKey: ["silo-spawn-requests"],
    queryFn: fetchSiloSpawnRequests,
    enabled: Boolean(isSignedIn && isAdmin),
    refetchInterval: 30_000,
  });

  const requests = useMemo(
    () =>
      [...(requestsQuery.data ?? [])].sort((left, right) => {
        const priorityDelta = priorityRank[left.priority] - priorityRank[right.priority];
        if (priorityDelta !== 0) return priorityDelta;
        return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
      }),
    [requestsQuery.data],
  );
  const boardsQuery = useQuery({
    queryKey: ["boards", "silo-requests"],
    queryFn: fetchBoardOptions,
    enabled: Boolean(isSignedIn && isAdmin),
    refetchInterval: 60_000,
  });
  const boardNameById = useMemo(
    () => new Map((boardsQuery.data ?? []).map((board) => [board.id, board.name])),
    [boardsQuery.data],
  );

  const createMutation = useMutation({
    mutationFn: createSiloSpawnRequest,
    onSuccess: async () => {
      setDisplayName("");
      setScope("organization");
      setPriority("normal");
      setBoardId("");
      setSourceTaskId("");
      setSourceTaskTitle("");
      setDesiredRole("");
      setRuntimePreference("");
      setSummary("");
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["silo-spawn-requests"] });
    },
    onError: (nextError) => {
      setError(nextError instanceof Error ? nextError.message : "Failed to create silo request.");
    },
  });
  const updateMutation = useMutation({
    mutationFn: async (input: { requestId: string; status: "planned" | "cancelled" | "requested" }) =>
      updateSiloSpawnRequest(input.requestId, { status: input.status }),
    onMutate: (input) => {
      setUpdatingRequestId(input.requestId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["silo-spawn-requests"] });
    },
    onSettled: () => {
      setUpdatingRequestId(null);
    },
    onError: (nextError) => {
      setError(nextError instanceof Error ? nextError.message : "Failed to update silo request.");
    },
  });

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to manage silo requests.",
        forceRedirectUrl: "/silos/requests",
      }}
      title="Silo requests"
      description="Track requested operating silos before they are provisioned into concrete runtime topology."
      isAdmin={isAdmin}
      adminOnlyMessage="Only organization owners and admins can manage silo requests."
      stickyHeader
    >
      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Card className="border border-slate-200">
          <CardHeader>
            <h2 className="text-lg font-semibold text-slate-900">Request a silo</h2>
            <p className="mt-1 text-sm text-slate-500">
              Start with a lightweight request before wiring the full runtime shape.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="silo-request-name">Display name</Label>
              <Input
                id="silo-request-name"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Research pod"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="silo-request-kind">Silo shape</Label>
              <select
                id="silo-request-kind"
                className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
                value={siloKind}
                onChange={(event) => setSiloKind(event.target.value)}
              >
                {KIND_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="silo-request-scope">Scope</Label>
              <select
                id="silo-request-scope"
                className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
                value={scope}
                onChange={(event) => {
                  const nextScope = event.target.value as Extract<
                    SiloSpawnRequestScope,
                    "organization" | "board"
                  >;
                  setScope(nextScope);
                  if (nextScope !== "board") {
                    setBoardId("");
                    setSourceTaskId("");
                    setSourceTaskTitle("");
                  }
                }}
              >
                <option value="organization">Organization</option>
                <option value="board">Board</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="silo-request-priority">Priority</Label>
              <select
                id="silo-request-priority"
                className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
                value={priority}
                onChange={(event) => setPriority(event.target.value as SiloSpawnRequestPriority)}
              >
                {PRIORITY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            {scope === "board" ? (
              <div className="space-y-2">
                <Label htmlFor="silo-request-board">Board</Label>
                <select
                  id="silo-request-board"
                  className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
                  value={boardId}
                  onChange={(event) => setBoardId(event.target.value)}
                >
                  <option value="">Select board</option>
                  {(boardsQuery.data ?? []).map((board) => (
                    <option key={board.id} value={board.id}>
                      {board.name}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
            {sourceTaskTitle ? (
              <div className="rounded-xl border border-blue-200 bg-blue-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">
                  Demand source task
                </p>
                <p className="mt-1 text-sm font-medium text-slate-900">{sourceTaskTitle}</p>
                <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-600">
                  <span>This request was opened from a task workload context.</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-auto px-0 py-0 text-blue-700 hover:bg-transparent hover:text-blue-900"
                    onClick={() => {
                      setSourceTaskId("");
                      setSourceTaskTitle("");
                    }}
                  >
                    Clear task context
                  </Button>
                </div>
              </div>
            ) : null}
            <div className="space-y-2">
              <Label htmlFor="silo-request-role">Desired role</Label>
              <Input
                id="silo-request-role"
                value={desiredRole}
                onChange={(event) => setDesiredRole(event.target.value)}
                placeholder="research, reviewer, planner"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="silo-request-runtime">Runtime preference</Label>
              <Input
                id="silo-request-runtime"
                value={runtimePreference}
                onChange={(event) => setRuntimePreference(event.target.value)}
                placeholder="symphony, gateway, hybrid"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="silo-request-summary">Summary</Label>
              <textarea
                id="silo-request-summary"
                className="min-h-28 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                value={summary}
                onChange={(event) => setSummary(event.target.value)}
                placeholder="Why this silo exists and what work it should own."
              />
            </div>
            {error ? <p className="text-sm text-red-500">{error}</p> : null}
            <Button
              className="w-full"
              disabled={
                createMutation.isPending ||
                displayName.trim().length === 0 ||
                (scope === "board" && boardId.length === 0)
              }
              onClick={() =>
                createMutation.mutate({
                  display_name: displayName,
                  silo_kind: siloKind,
                  scope,
                  priority,
                  board_id: scope === "board" ? boardId : null,
                  source_task_id: scope === "board" && sourceTaskId ? sourceTaskId : null,
                  desired_role: desiredRole || null,
                  source_task_title: sourceTaskTitle || null,
                  runtime_preference: runtimePreference || null,
                  summary: summary || null,
                })
              }
            >
              {createMutation.isPending ? "Requesting…" : "Create silo request"}
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {requestsQuery.isLoading ? (
            <Card>
              <CardHeader>
                <h2 className="text-lg font-semibold text-slate-900">Loading silo requests</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Fetching current requested silos and their desired state.
                </p>
              </CardHeader>
            </Card>
          ) : requests.length === 0 ? (
            <Card>
              <CardHeader>
                <h2 className="text-lg font-semibold text-slate-900">No silo requests yet</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Requested silos will appear here before they become provisioned operating silos.
                </p>
              </CardHeader>
            </Card>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {requests.map((request) => (
                <Card key={request.id} className="border border-slate-200">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h2 className="text-lg font-semibold text-slate-900">
                          {request.display_name}
                        </h2>
                        <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400">
                          {request.silo_kind} · {request.scope}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs font-medium ${priorityPillClass(request.priority)}`}
                        >
                          {request.priority}
                        </span>
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                          {request.status}
                        </span>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm text-slate-600">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Role</p>
                        <p className="mt-1 font-medium text-slate-900">
                          {request.desired_role ?? "Unspecified"}
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Scope</p>
                        <p className="mt-1 font-medium text-slate-900">
                          {request.scope}
                        </p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Runtime</p>
                        <p className="mt-1 font-medium text-slate-900">
                          {request.runtime_preference ?? "Unspecified"}
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Target</p>
                        <p className="mt-1 font-medium text-slate-900">
                          {request.board_id
                            ? (boardNameById.get(request.board_id) ?? "Board scope")
                            : "Organization"}
                        </p>
                      </div>
                    </div>
                    {request.source_task_title ? (
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Demand</p>
                        <p className="mt-1 font-medium text-slate-900">
                          {request.source_task_title}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {describeSiloRequestPressure(request) ?? "Linked task demand"}
                        </p>
                      </div>
                    ) : null}
                    <p>{request.summary ?? "No summary yet."}</p>
                    {request.materialized_silo_id ? (
                      <Link
                        href={`/silos/${request.materialized_silo_slug ?? request.slug}`}
                        className={buttonVariants({ variant: "secondary", size: "sm" })}
                      >
                        Open silo
                      </Link>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        <Link
                          href={`/silos/new?request=${request.id}`}
                          className={buttonVariants({ variant: "secondary", size: "sm" })}
                        >
                          Open create flow
                        </Link>
                        {request.status === "requested" ? (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={updatingRequestId === request.id}
                            onClick={() =>
                              updateMutation.mutate({ requestId: request.id, status: "planned" })
                            }
                          >
                            Plan
                          </Button>
                        ) : null}
                        {(request.status === "requested" || request.status === "planned") ? (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={updatingRequestId === request.id}
                            onClick={() =>
                              updateMutation.mutate({
                                requestId: request.id,
                                status: "cancelled",
                              })
                            }
                          >
                            Cancel
                          </Button>
                        ) : null}
                        {(request.status === "cancelled" || request.status === "failed") ? (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={updatingRequestId === request.id}
                            onClick={() =>
                              updateMutation.mutate({
                                requestId: request.id,
                                status: "requested",
                              })
                            }
                          >
                            Reopen
                          </Button>
                        ) : null}
                      </div>
                    )}
                    {request.materialized_at ? (
                      <p className="text-xs text-emerald-600">
                        Materialized {new Date(request.materialized_at).toLocaleString()}
                      </p>
                    ) : null}
                    {isOpenSiloRequestStatus(request.status) && request.source_task_status ? (
                      <p className="text-xs text-slate-500">
                        Demand snapshot: {request.source_task_status}
                        {request.source_task_priority
                          ? ` · ${request.source_task_priority}`
                          : ""}
                      </p>
                    ) : null}
                    <p className="text-xs text-slate-400">
                      Updated {new Date(request.updated_at).toLocaleString()}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {requestsQuery.error ? (
            <p className="text-sm text-red-500">
              {requestsQuery.error instanceof Error
                ? requestsQuery.error.message
                : "Failed to load silo requests."}
            </p>
          ) : null}
        </div>
      </div>
    </DashboardPageLayout>
  );
}
