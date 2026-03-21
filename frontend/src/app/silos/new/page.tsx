"use client";

export const dynamic = "force-dynamic";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";

import { useAuth } from "@/auth/clerk";
import { ApiError } from "@/api/mutator";
import {
  type listGatewaysApiV1GatewaysGetResponse,
  useListGatewaysApiV1GatewaysGet,
} from "@/api/generated/gateways/gateways";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { createSilo, fetchSiloBlueprints } from "@/lib/silos";

const DEFAULT_BLUEPRINT = "default-four-agent";

export default function NewSiloPage() {
  const router = useRouter();
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);

  const [name, setName] = useState("");
  const [enableSymphony, setEnableSymphony] = useState(false);
  const [enableTelemetry, setEnableTelemetry] = useState(true);
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const blueprintsQuery = useQuery({
    queryKey: ["silo-blueprints"],
    queryFn: fetchSiloBlueprints,
    enabled: Boolean(isSignedIn && isAdmin),
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

  const blueprint = useMemo(
    () =>
      (blueprintsQuery.data ?? []).find((item) => item.slug === DEFAULT_BLUEPRINT) ??
      null,
    [blueprintsQuery.data],
  );
  const roles = useMemo(
    () => (blueprint?.roles ?? []).filter((role) => role.runtime_kind === "gateway"),
    [blueprint?.roles],
  );
  const gateways =
    gatewaysQuery.data?.status === 200 ? (gatewaysQuery.data.data.items ?? []) : [];

  const createMutation = useMutation({
    mutationFn: createSilo,
    onSuccess: (result) => {
      router.push(`/silos/${result.slug}`);
    },
    onError: (nextError) => {
      setError(nextError instanceof Error ? nextError.message : "Failed to create silo.");
    },
  });

  const isLoading =
    blueprintsQuery.isLoading || gatewaysQuery.isLoading || createMutation.isPending;

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim()) {
      setError("Silo name is required.");
      return;
    }
    if (!blueprint) {
      setError("Default silo blueprint is unavailable.");
      return;
    }
    setError(null);
    createMutation.mutate({
      name: name.trim(),
      blueprint_slug: blueprint.slug,
      enable_symphony: enableSymphony,
      enable_telemetry: enableTelemetry,
      gateway_assignments: roles
        .map((role) => ({
          role_slug: role.slug,
          gateway_id: assignments[role.slug] || null,
        }))
        .filter((assignment) => assignment.gateway_id),
    });
  };

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to create a silo.",
        forceRedirectUrl: "/silos/new",
      }}
      title="Create silo"
      description="Persist a new silo from the default four-agent blueprint and assign runtime gateways."
      isAdmin={isAdmin}
      adminOnlyMessage="Only organization owners and admins can create silos."
    >
      <form
        onSubmit={handleSubmit}
        className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <Card className="border border-slate-100 bg-slate-50">
          <CardHeader>
            <h2 className="text-lg font-semibold text-slate-900">Blueprint</h2>
            <p className="mt-1 text-sm text-slate-500">
              {blueprint
                ? `${blueprint.display_name} · ${blueprint.version}`
                : "Loading default blueprint"}
            </p>
          </CardHeader>
          {blueprint?.description ? (
            <CardContent>
              <p className="text-sm text-slate-600">{blueprint.description}</p>
            </CardContent>
          ) : null}
        </Card>

        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-900">
              Silo name <span className="text-red-500">*</span>
            </label>
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Launch Crew"
              disabled={isLoading}
            />
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-medium text-slate-900">Add-ons</p>
            <div className="mt-3 space-y-3 text-sm text-slate-700">
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={enableTelemetry}
                  onChange={(event) => setEnableTelemetry(event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300"
                />
                Enable telemetry
              </label>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={enableSymphony}
                  onChange={(event) => setEnableSymphony(event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300"
                />
                Enable Symphony
              </label>
            </div>
          </div>
        </div>

        <div>
          <h2 className="text-lg font-semibold text-slate-900">Gateway assignments</h2>
          <p className="mt-1 text-sm text-slate-500">
            Assign gateways to runtime roles now, or leave them unassigned and fix them in silo detail.
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {roles.map((role) => (
              <Card key={role.slug}>
                <CardHeader>
                  <h3 className="text-base font-semibold text-slate-900">{role.display_name}</h3>
                  <p className="mt-1 text-sm text-slate-500">{role.role_type}</p>
                </CardHeader>
                <CardContent>
                  <Select
                    value={assignments[role.slug] ?? "__unassigned__"}
                    onValueChange={(value) =>
                      setAssignments((current) => ({
                        ...current,
                        [role.slug]: value === "__unassigned__" ? "" : value,
                      }))
                    }
                    disabled={isLoading}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select gateway" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__unassigned__">Unassigned</SelectItem>
                      {gateways.map((gateway) => (
                        <SelectItem key={gateway.id} value={gateway.id}>
                          {gateway.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {error ? <p className="text-sm text-red-500">{error}</p> : null}
        {blueprintsQuery.error ? (
          <p className="text-sm text-red-500">
            {blueprintsQuery.error instanceof Error
              ? blueprintsQuery.error.message
              : "Failed to load silo blueprints."}
          </p>
        ) : null}
        {gatewaysQuery.error ? (
          <p className="text-sm text-red-500">
            {gatewaysQuery.error.message || "Failed to load gateways."}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={isLoading || !isAdmin}>
            {createMutation.isPending ? "Creating…" : "Create silo"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => router.push("/silos")}
            disabled={isLoading}
          >
            Cancel
          </Button>
        </div>
      </form>
    </DashboardPageLayout>
  );
}
