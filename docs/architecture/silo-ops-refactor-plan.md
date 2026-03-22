# Silo Ops Refactor Plan

## Goal

Refactor the silo-centric operator experience toward a centralized `policy + shared view-model`
structure without changing backend contracts or broad product behavior.

This is a safety-first refactor. The primary objective is to reduce duplicated UI decision logic
across:

- dashboard
- silos overview
- silo detail
- task dispatch

## Scope

This refactor is limited to frontend decision and presentation-model code.

In scope:

- shared silo health taxonomy
- shared dispatch-fit policy
- shared task demand classification
- shared view-model shaping for dashboard, silos overview, silo detail, and task dispatch

Out of scope for this pass:

- backend schema redesign
- API contract changes
- new operator workflows
- LLM-based routing or recommendation

## Safety Rules

1. Preserve existing behavior before improving vocabulary or structure.
2. Move logic behind shared helpers before changing UI flows.
3. Keep backend payloads unchanged in this pass.
4. Prefer additive wrappers over deleting working code immediately.
5. Keep each slice small enough to lint and reason about independently.

## Target Structure

Create a dedicated frontend module:

- `frontend/src/lib/silo-ops/health.ts`
- `frontend/src/lib/silo-ops/demand.ts`
- `frontend/src/lib/silo-ops/dispatch.ts`
- `frontend/src/lib/silo-ops/view-models.ts`

Responsibility split:

- `health.ts`
  - central silo health taxonomy
  - health labels, tones, and guidance
- `demand.ts`
  - task demand classification
  - demand labels, tones, and reasons
- `dispatch.ts`
  - deterministic dispatch fit scoring
  - candidate ranking
- `view-models.ts`
  - dashboard summary rows
  - silos overview cards
  - silo detail operator summary
  - task dispatch recommendation view-model

## Migration Plan

### Slice 1

Move the existing health taxonomy, task demand logic, and dispatch scoring into `silo-ops`
modules with no intentional behavior change.

### Slice 2

Replace page-local shaping in:

- dashboard
- silos overview
- silo detail
- task dispatch

with shared view-model builders.

### Slice 3

Remove leftover duplicated helper paths and rename old entry points into thin compatibility
wrappers if needed.

## Success Criteria

- dashboard, silos overview, silo detail, and task dispatch use the same silo state language
- page files mostly render prepared view-models instead of computing operator policy inline
- no backend contract changes are required
- frontend lint passes after each slice

## Deferred Work

After this refactor stabilizes, the next step can be to decide whether some of the shared
frontend policy should be promoted into backend-provided operational snapshots.
