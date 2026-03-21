"use client";

export function RuntimeRunMetaGrid({
  details,
  itemKey,
}: {
  details: Array<{ label: string; value: string }>;
  itemKey: string;
}) {
  if (details.length === 0) return null;

  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      {details.map((detail) => (
        <div
          key={`${itemKey}-${detail.label}-${detail.value}`}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
        >
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            {detail.label}
          </p>
          <p className="mt-1 break-words text-sm text-slate-700">{detail.value}</p>
        </div>
      ))}
    </div>
  );
}
