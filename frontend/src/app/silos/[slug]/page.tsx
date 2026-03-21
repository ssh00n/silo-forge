"use client";

export const dynamic = "force-dynamic";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/clerk";
import { ApiError } from "@/api/mutator";
import {
  type listGatewaysApiV1GatewaysGetResponse,
  useListGatewaysApiV1GatewaysGet,
} from "@/api/generated/gateways/gateways";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  UNASSIGNED_GATEWAY,
  collectSiloWarnings,
  getAssignedGatewayRoleCount,
  getBlockedProvisionTargetCount,
  getReadyProvisionTargetCount,
  hasActionableProvisionTargets,
  hasSiloConfigChanges,
} from "@/lib/silo-detail";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { fetchSiloDetail, runSiloRuntime, updateSilo } from "@/lib/silos";

function formatRoleTitle(roleType: string) {
  return roleType.replaceAll("_", " ");
}

export default function SiloDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = typeof params?.slug === "string" ? params.slug : "";
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);
  const queryClient = useQueryClient();
  const [runtimeMessage, setRuntimeMessage] = useState<string | null>(null);
  const [assignmentDrafts, setAssignmentDrafts] = useState<Record<string, string>>({});
  const [enableSymphonyDraft, setEnableSymphonyDraft] = useState<boolean | null>(null);
  const [enableTelemetryDraft, setEnableTelemetryDraft] = useState<boolean | null>(null);

  const detailQuery = useQuery({
    queryKey: ["silos", slug, "detail"],
    queryFn: () => fetchSiloDetail(slug),
    enabled: Boolean(slug && isSignedIn && isAdmin),
    refetchInterval: 30_000,
  });
  const gatewaysQuery = useListGatewaysApiV1GatewaysGet<
    listGatewaysApiV1GatewaysGetResponse,
    ApiError
  >(undefined, {
    query: {
      enabled: Boolean(isSignedIn && isAdmin),
      refetchOnMount: "always",
    },
  });

  const runtimeMutation = useMutation({
    mutationFn: async (mode: "validate" | "apply") => runSiloRuntime(slug, mode),
    onSuccess: (result) => {
      const successful = result.results.filter(
        (item) =>
          (result.mode === "validate" && item.validated?.valid) ||
          (result.mode === "apply" && item.applied?.applied),
      ).length;
      setRuntimeMessage(`${result.mode} completed for ${successful} assigned role(s).`);
      void queryClient.invalidateQueries({ queryKey: ["silos", slug, "detail"] });
    },
    onError: (error) => {
      setRuntimeMessage(error instanceof Error ? error.message : "Runtime operation failed.");
    },
  });
  const assignmentMutation = useMutation({
    mutationFn: async () =>
      updateSilo(slug, {
        enable_symphony: enableSymphonyDraft ?? undefined,
        enable_telemetry: enableTelemetryDraft ?? undefined,
        gateway_assignments: roleCards.map((role) => ({
          role_slug: role.slug,
          gateway_id:
            assignmentDrafts[role.slug] === UNASSIGNED_GATEWAY
              ? null
              : (assignmentDrafts[role.slug] ?? role.gateway_id ?? null),
        })),
      }),
    onSuccess: () => {
      setRuntimeMessage("Assignments saved.");
      setAssignmentDrafts({});
      setEnableSymphonyDraft(null);
      setEnableTelemetryDraft(null);
      void queryClient.invalidateQueries({ queryKey: ["silos", slug, "detail"] });
    },
    onError: (error) => {
      setRuntimeMessage(error instanceof Error ? error.message : "Failed to save assignments.");
    },
  });

  const detail = detailQuery.data;
  const roleCards = detail?.roles ?? [];
  const gateways =
    gatewaysQuery.data?.status === 200 ? (gatewaysQuery.data.data.items ?? []) : [];
  const warningItems = useMemo(
    () => (detail ? collectSiloWarnings(detail) : []),
    [detail],
  );
  const assignedGatewayRoleCount = detail ? getAssignedGatewayRoleCount(detail) : 0;
  const readyTargetCount = detail ? getReadyProvisionTargetCount(detail) : 0;
  const blockedTargetCount = detail ? getBlockedProvisionTargetCount(detail) : 0;
  const canApplyRuntime = detail ? hasActionableProvisionTargets(detail) : false;
  const configDirty = detail
    ? hasSiloConfigChanges({
        detail,
        assignmentDrafts,
        enableSymphonyDraft,
        enableTelemetryDraft,
      })
    : false;

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to view silo detail.",
        forceRedirectUrl: `/silos/${slug}`,
      }}
      title={detail?.silo.name ?? "Silo detail"}
      description={
        detail
          ? `${detail.silo.blueprint_slug}@${detail.silo.blueprint_version} · ${detail.silo.status}`
          : "Loading silo detail."
      }
      headerActions={
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={() => runtimeMutation.mutate("validate")}
            disabled={runtimeMutation.isPending || !isAdmin}
          >
            Validate runtime
          </Button>
          <Button
            onClick={() => runtimeMutation.mutate("apply")}
            disabled={runtimeMutation.isPending || !isAdmin || !canApplyRuntime}
          >
            Apply runtime
          </Button>
        </div>
      }
      isAdmin={isAdmin}
      adminOnlyMessage="Only organization owners and admins can access silos."
      stickyHeader
    >
      <div className="mb-4">
        <Link href="/silos" className="text-sm font-medium text-blue-700 hover:text-blue-900">
          Back to silos
        </Link>
      </div>

      {detailQuery.isError ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-red-500">
              {detailQuery.error instanceof Error
                ? detailQuery.error.message
                : "Failed to load silo detail."}
            </p>
          </CardContent>
        </Card>
      ) : null}

      {runtimeMessage ? (
        <div className="mb-4 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
          {runtimeMessage}
        </div>
      ) : null}

      {warningItems.length > 0 ? (
        <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-amber-900">Operator attention needed</p>
              <p className="mt-1 text-sm text-amber-800">
                Review these warnings before applying runtime changes.
              </p>
            </div>
            <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-900">
              {warningItems.length} warning{warningItems.length === 1 ? "" : "s"}
            </span>
          </div>
          <ul className="mt-3 space-y-2 text-sm text-amber-900">
            {warningItems.slice(0, 6).map((warning) => (
              <li key={warning} className="rounded-xl bg-white/70 px-3 py-2">
                {warning}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {!slug ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-slate-500">Silo slug is missing.</p>
          </CardContent>
        </Card>
      ) : null}

      {detailQuery.isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-slate-500">
              Loading silo detail and latest provision plan.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {detail ? (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Roles</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-900">{detail.silo.role_count}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Telemetry</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-900">
                  {detail.silo.enable_telemetry ? "On" : "Off"}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Symphony</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-900">
                  {detail.silo.enable_symphony ? "On" : "Off"}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Runtime Ready</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-900">
                  {readyTargetCount}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Blocked</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-900">{blockedTargetCount}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Assigned</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-900">
                  {assignedGatewayRoleCount}
                </p>
              </CardContent>
            </Card>
          </div>

          <Tabs defaultValue="roles" className="mt-6">
            <TabsList>
              <TabsTrigger value="roles">Roles</TabsTrigger>
              <TabsTrigger value="config">Config</TabsTrigger>
              <TabsTrigger value="operations">Operations</TabsTrigger>
            </TabsList>

            <TabsContent value="roles">
              <div className="grid gap-4 xl:grid-cols-[1.15fr,0.85fr]">
                <div className="grid gap-4 lg:grid-cols-2">
                  {roleCards.map((role) => (
                    <Card key={role.slug}>
                      <CardHeader>
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <h2 className="text-lg font-semibold text-slate-900">{role.display_name}</h2>
                            <p className="mt-1 text-sm text-slate-500">{formatRoleTitle(role.role_type)}</p>
                          </div>
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                            {role.runtime_kind}
                          </span>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-3 text-sm text-slate-600">
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div>
                            <p className="text-xs uppercase tracking-wide text-slate-400">Gateway</p>
                            <p className="mt-1 font-medium text-slate-900">
                              {role.gateway_name ?? "Unassigned"}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-wide text-slate-400">Workspace</p>
                            <p className="mt-1 font-medium text-slate-900">
                              {role.workspace_root ?? "Not set"}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-wide text-slate-400">Model</p>
                            <p className="mt-1 font-medium text-slate-900">
                              {role.default_model ?? "Default"}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-wide text-slate-400">Channel</p>
                            <p className="mt-1 font-medium text-slate-900">
                              {role.channel_name ?? "None"}
                            </p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
                <Card>
                  <CardHeader>
                    <h2 className="text-lg font-semibold text-slate-900">Edit assignments</h2>
                    <p className="mt-1 text-sm text-slate-500">
                      Update role-to-gateway mapping before reprovisioning.
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-sm font-medium text-slate-900">Add-ons</p>
                      <div className="mt-3 space-y-3 text-sm text-slate-700">
                        <label className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={enableTelemetryDraft ?? detail.silo.enable_telemetry}
                            onChange={(event) => setEnableTelemetryDraft(event.target.checked)}
                            className="h-4 w-4 rounded border-slate-300"
                          />
                          Enable telemetry
                        </label>
                        <label className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={enableSymphonyDraft ?? detail.silo.enable_symphony}
                            onChange={(event) => setEnableSymphonyDraft(event.target.checked)}
                            className="h-4 w-4 rounded border-slate-300"
                          />
                          Enable Symphony
                        </label>
                      </div>
                    </div>
                    {roleCards
                      .filter((role) => role.runtime_kind === "gateway")
                      .map((role) => (
                        <div key={role.slug} className="space-y-2">
                          <label className="text-sm font-medium text-slate-900">
                            {role.display_name}
                          </label>
                          <Select
                            value={
                              assignmentDrafts[role.slug] ??
                              role.gateway_id ??
                              UNASSIGNED_GATEWAY
                            }
                            onValueChange={(value) =>
                              setAssignmentDrafts((current) => ({
                                ...current,
                                [role.slug]: value,
                              }))
                            }
                            disabled={assignmentMutation.isPending}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select gateway" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value={UNASSIGNED_GATEWAY}>Unassigned</SelectItem>
                              {gateways.map((gateway) => (
                                <SelectItem key={gateway.id} value={gateway.id}>
                                  {gateway.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      ))}
                    <Button
                      variant="secondary"
                      onClick={() => assignmentMutation.mutate()}
                      disabled={assignmentMutation.isPending || !configDirty}
                    >
                      {assignmentMutation.isPending ? "Saving…" : "Save configuration"}
                    </Button>
                    {!configDirty ? (
                      <p className="text-xs text-slate-500">
                        No unsaved add-on or assignment changes.
                      </p>
                    ) : null}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="config">
              <div className="grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
                <Card>
                  <CardHeader>
                    <h2 className="text-lg font-semibold text-slate-900">Desired state warnings</h2>
                  </CardHeader>
                  <CardContent>
                    {detail.desired_state.warnings.length === 0 ? (
                      <p className="text-sm text-slate-500">No desired-state warnings.</p>
                    ) : (
                      <ul className="space-y-2 text-sm text-slate-700">
                        {detail.desired_state.warnings.map((warning) => (
                          <li key={warning} className="rounded-xl bg-amber-50 px-3 py-2">
                            {warning}
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <h2 className="text-lg font-semibold text-slate-900">Shared secret bindings</h2>
                  </CardHeader>
                  <CardContent>
                    {detail.desired_state.shared_secret_bindings.length === 0 ? (
                      <p className="text-sm text-slate-500">No shared secret bindings.</p>
                    ) : (
                      <div className="space-y-3 text-sm">
                        {detail.desired_state.shared_secret_bindings.map((binding) => (
                          <div key={binding.name} className="rounded-xl bg-slate-50 p-3">
                            <p className="font-medium text-slate-900">{binding.name}</p>
                            <p className="mt-1 text-slate-500">
                              {binding.vault_path}:{binding.vault_key}
                            </p>
                            <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">
                              env {binding.env_var}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <h2 className="text-lg font-semibold text-slate-900">Role secret bindings</h2>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm">
                    {detail.roles.map((role) => (
                      <div key={role.slug} className="rounded-xl bg-slate-50 p-3">
                        <p className="font-medium text-slate-900">{role.display_name}</p>
                        {role.secret_bindings.length === 0 ? (
                          <p className="mt-1 text-slate-500">No role-specific bindings.</p>
                        ) : (
                          <div className="mt-2 space-y-2">
                            {role.secret_bindings.map((binding) => (
                              <div key={`${role.slug}-${binding.name}`}>
                                <p className="text-slate-700">{binding.name}</p>
                                <p className="text-xs uppercase tracking-wide text-slate-400">
                                  env {binding.env_var}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="operations">
              <div className="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
                <Card>
                  <CardHeader>
                    <h2 className="text-lg font-semibold text-slate-900">Provision targets</h2>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {detail.provision_plan?.targets.length ? (
                      detail.provision_plan.targets.map((target) => (
                        <div key={target.role_slug} className="rounded-xl border border-slate-200 p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="font-medium text-slate-900">{target.role_slug}</p>
                              <p className="mt-1 text-sm text-slate-500">
                                {target.gateway_name ?? "Unassigned"} · {target.workspace_root ?? "No workspace"}
                              </p>
                            </div>
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                              {target.supports_picoclaw_bundle_apply ? "ready" : "blocked"}
                            </span>
                          </div>
                          {target.warnings.length > 0 ? (
                            <div className="mt-3 space-y-2">
                              {target.warnings.map((warning) => (
                                <p key={warning} className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-slate-700">
                                  {warning}
                                </p>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">No provision targets are available yet.</p>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <h2 className="text-lg font-semibold text-slate-900">Latest runtime result</h2>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm text-slate-600">
                    {detail.latest_runtime_operation ? (
                      <>
                        <div className="rounded-xl bg-slate-50 p-3">
                          <p className="text-xs uppercase tracking-wide text-slate-400">Mode</p>
                          <p className="mt-1 font-medium text-slate-900">
                            {detail.latest_runtime_operation.mode}
                          </p>
                        </div>
                        <div className="rounded-xl bg-slate-50 p-3">
                          <p className="text-xs uppercase tracking-wide text-slate-400">Recorded</p>
                          <p className="mt-1 font-medium text-slate-900">
                            {new Date(detail.latest_runtime_operation.created_at).toLocaleString()}
                          </p>
                        </div>
                        <div className="space-y-2">
                          {detail.latest_runtime_operation.results.map((result) => (
                            <div key={result.role_slug} className="rounded-xl border border-slate-200 p-3">
                              <div className="flex items-center justify-between gap-3">
                                <p className="font-medium text-slate-900">{result.role_slug}</p>
                                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                                  {result.validated?.valid || result.applied?.applied
                                    ? "ok"
                                    : result.supports_picoclaw_bundle_apply
                                      ? "ran"
                                      : "blocked"}
                                </span>
                              </div>
                              {result.warnings.length > 0 ? (
                                <p className="mt-2 text-xs text-amber-700">
                                  {result.warnings.join(" · ")}
                                </p>
                              ) : null}
                            </div>
                          ))}
                        </div>
                        {detail.latest_runtime_operation.warnings.length > 0 ? (
                          <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
                            {detail.latest_runtime_operation.warnings.join(" · ")}
                          </div>
                        ) : null}
                      </>
                    ) : (
                      <>
                        <p>No runtime operation has been recorded yet.</p>
                        <p>Run validate first, then apply once assignments and warnings look correct.</p>
                      </>
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </>
      ) : null}
    </DashboardPageLayout>
  );
}
