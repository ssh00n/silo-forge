export function BrandMark() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-10 w-10 place-items-center rounded-lg bg-gradient-to-br from-blue-600 to-blue-700 text-xs font-semibold text-white shadow-sm">
        <span className="font-heading tracking-[0.2em]">SF</span>
      </div>
      <div className="leading-tight">
        <div className="font-heading text-sm uppercase tracking-[0.26em] text-strong">
          SILO FORGE
        </div>
        <div className="text-[11px] font-medium text-quiet">
          Agent Control Plane
        </div>
      </div>
    </div>
  );
}
