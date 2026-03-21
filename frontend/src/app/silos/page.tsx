"use client";

export const dynamic = "force-dynamic";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/auth/clerk";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { fetchSilos } from "@/lib/silos";

export default function SilosPage() {
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);

  const silosQuery = useQuery({
    queryKey: ["silos"],
    queryFn: fetchSilos,
    enabled: Boolean(isSignedIn && isAdmin),
    refetchInterval: 30_000,
  });

  const silos = useMemo(() => silosQuery.data ?? [], [silosQuery.data]);

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to view silos.",
        forceRedirectUrl: "/silos",
      }}
      title="Silos"
      description="Track provisioned silo factories, blueprint versions, and runtime readiness."
      headerActions={
        isAdmin ? (
          <Link
            href="/silos/new"
            className={buttonVariants({ size: "md", variant: "primary" })}
          >
            Create silo
          </Link>
        ) : null
      }
      isAdmin={isAdmin}
      adminOnlyMessage="Only organization owners and admins can access silos."
      stickyHeader
    >
      {silosQuery.isLoading ? (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-slate-900">Loading silos</h2>
            <p className="mt-1 text-sm text-slate-500">
              Fetching persisted silos and their latest status.
            </p>
          </CardHeader>
        </Card>
      ) : silos.length === 0 ? (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-slate-900">No silos yet</h2>
            <p className="mt-1 text-sm text-slate-500">
              Persisted silos will appear here once the create flow is wired into the UI.
            </p>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {silos.map((silo) => (
            <Link key={silo.slug} href={`/silos/${silo.slug}`}>
              <Card className="h-full border border-slate-200 transition hover:-translate-y-0.5 hover:border-blue-300">
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold text-slate-900">{silo.name}</h2>
                      <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400">
                        {silo.blueprint_slug}@{silo.blueprint_version}
                      </p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                      {silo.status}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-xl bg-slate-50 p-3">
                      <p className="text-xs uppercase tracking-wide text-slate-400">Roles</p>
                      <p className="mt-1 text-base font-semibold text-slate-900">
                        {silo.role_count}
                      </p>
                    </div>
                    <div className="rounded-xl bg-slate-50 p-3">
                      <p className="text-xs uppercase tracking-wide text-slate-400">Telemetry</p>
                      <p className="mt-1 text-base font-semibold text-slate-900">
                        {silo.enable_telemetry ? "On" : "Off"}
                      </p>
                    </div>
                  </div>
                  <span
                    className={buttonVariants({
                      variant: "secondary",
                      size: "sm",
                      className: "w-full pointer-events-none",
                    })}
                  >
                    Open silo detail
                  </span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {silosQuery.error ? (
        <p className="mt-4 text-sm text-red-500">
          {silosQuery.error instanceof Error
            ? silosQuery.error.message
            : "Failed to load silos."}
        </p>
      ) : null}
    </DashboardPageLayout>
  );
}
