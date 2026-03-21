"use client";

import { cn } from "@/lib/utils";
import { runtimeRunStatusClass } from "@/lib/runtime-runs";

export function RuntimeRunStatusChip({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        runtimeRunStatusClass(status),
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
