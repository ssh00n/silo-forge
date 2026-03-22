"use client";

export const dynamic = "force-dynamic";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/auth/clerk";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  buildSiloOverviewCards,
  buildSiloOverviewSummaryViewModel,
  siloReasonChipClass,
  siloToneBadgeVariant,
} from "@/lib/silo-dispatch";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { fetchSilos } from "@/lib/silos";
import { Badge } from "@/components/ui/badge";

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
  const siloSummary = useMemo(() => buildSiloOverviewSummaryViewModel(silos), [silos]);
  const siloCards = useMemo(() => buildSiloOverviewCards(silos), [silos]);

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to view silos.",
        forceRedirectUrl: "/silos",
      }}
      title="Silos"
      description="Operate silo health, readiness, and runtime posture before planning additional capacity."
      headerActions={
        isAdmin ? (
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/silos/new"
              className={buttonVariants({ size: "md", variant: "primary" })}
            >
              Create silo
            </Link>
            <Link
              href="/silos/requests"
              className={buttonVariants({ size: "md", variant: "secondary" })}
            >
              Silo requests
            </Link>
          </div>
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
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Total silos</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-900">{siloSummary.total}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Healthy</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-emerald-700">{siloSummary.healthy}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Busy</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-900">{siloSummary.busy}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Blocked</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-rose-700">{siloSummary.blocked}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Degraded</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-amber-700">{siloSummary.degraded}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Needs setup</p>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold text-slate-700">{siloSummary.needsSetup}</p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {siloCards.map((posture) => {
              const silo = posture.silo;
              return (
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
                      <Badge
                        variant={siloToneBadgeVariant(posture.tone)}
                        className="px-2.5 py-1 text-xs font-medium normal-case tracking-normal"
                      >
                        {posture.readinessLabel}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-slate-600">{posture.guidance}</p>
                    <div className="flex flex-wrap gap-2 text-[11px]">
                      {posture.reasons.slice(0, 3).map((reason) => (
                        <span
                          key={`${silo.slug}-${reason.label}`}
                          className={`rounded-full px-2.5 py-1 ${siloReasonChipClass(reason.tone)}`}
                        >
                          {reason.label}
                        </span>
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Roles</p>
                        <p className="mt-1 text-base font-semibold text-slate-900">
                          {silo.role_count}
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Active</p>
                        <p className="mt-1 text-base font-semibold text-slate-900">
                          {silo.active_run_count}
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Blocked</p>
                        <p className="mt-1 text-base font-semibold text-slate-900">
                          {silo.blocked_run_count}
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Failed</p>
                        <p className="mt-1 text-base font-semibold text-slate-900">
                          {silo.failed_run_count}
                        </p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Mode</p>
                        <p className="mt-1 text-base font-semibold text-slate-900">
                          {silo.enable_symphony ? "Symphony" : "Gateway"}
                        </p>
                      </div>
                    </div>
                    {silo.last_activity_at ? (
                      <p className="text-xs text-slate-500">
                        Last activity {new Date(silo.last_activity_at).toLocaleString()}
                      </p>
                    ) : null}
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
            )})}
          </div>
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
