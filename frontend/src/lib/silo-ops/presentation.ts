"use client";

import type { VariantProps } from "class-variance-authority";

import type { badgeVariants } from "@/components/ui/badge";

type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>;
type Tone = "success" | "warning" | "danger" | "neutral";

export const siloToneBadgeVariant = (tone: Tone): BadgeVariant => {
  if (tone === "success") return "success";
  if (tone === "warning") return "warning";
  if (tone === "danger") return "danger";
  return "default";
};

export const siloReasonChipClass = (tone: Tone): string => {
  if (tone === "success") return "bg-emerald-50 text-emerald-700";
  if (tone === "warning") return "bg-amber-50 text-amber-700";
  if (tone === "danger") return "bg-rose-50 text-rose-700";
  return "bg-slate-100 text-slate-700";
};
