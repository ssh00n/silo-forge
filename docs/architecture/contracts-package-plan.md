# Contracts Package Plan

This document locks the next architecture step for `Silo Forge`:

- keep each service independently deployable
- avoid hand-maintaining duplicate callback/request interfaces
- move toward a shared contract source-of-truth with generated artifacts

## Why now

The current system already spans multiple execution boundaries:

- `frontend` consumes activity, silo runtime, and execution-run payloads
- `backend` owns HTTP APIs, persistence, and callback ingest
- `symphony` emits execution callbacks and consumes dispatch requests
- future services will likely consume the same execution and activity contracts

That means the current duplication cost is still manageable, but already real.
This is the cheapest point to introduce a contract package.

## Decision

Use `contract package + generated artifacts`.

Do not use direct cross-repo imports of runtime types as the long-term approach.

Instead:

- define canonical schemas in one place
- generate service-local types from those schemas
- version the contract deliberately
- validate compatibility in CI

## Initial scope

Start with the narrowest high-value surface:

1. Symphony dispatch request
2. Symphony dispatch acceptance
3. Symphony callback payload
4. execution-run activity payload used by frontend surfaces
5. task and approval activity payloads used across feed surfaces

Do not try to centralize every model at once.

## Recommended structure

### Option A: in-repo `contracts/` first

Use this as the first step because it is the fastest:

```text
contracts/
  execution/
    dispatch.request.schema.json
    dispatch.acceptance.schema.json
    callback.payload.schema.json
  activity/
    execution-run.payload.schema.json
  openapi/
    execution-control-plane.openapi.yaml
  generated/
    typescript/
    python/
```

This keeps the source-of-truth inside the main product repo while the shape stabilizes.

### Option B: separate `silo-forge-contracts` package later

Move to a standalone package only after:

- the execution contracts stop changing every few days
- at least two repos consume the same generated artifacts in a repeatable way
- CI generation and versioning rules are stable

## Source-of-truth format

Use:

- `OpenAPI` for synchronous HTTP APIs
- `JSON Schema` for callback payloads and internal queue/job payloads

Add `AsyncAPI` only if event streaming contracts become a first-class public surface.

## Generated artifacts

### Frontend

- generated TypeScript types for dispatch/callback/activity payloads
- use these in `runtime-runs.ts`, `activity-events.ts`, and generated API responses where practical

### Backend

- generated Python typed models or validation helpers for callback payload validation
- use these at the callback boundary before persistence and activity logging

### Symphony

- generated TypeScript types for dispatch intake and callback emission
- use these instead of hand-maintained local interfaces

## Compatibility policy

Adopt these rules from the beginning:

- additive fields are allowed in minor contract revisions
- removing or renaming fields requires a breaking revision
- callback payloads must remain backward compatible for at least one product cycle
- generated artifacts must be reproducible from committed schema sources

## Immediate implementation phases

### Phase 1: execution contracts in main repo

- add `contracts/execution/*`
- codify current dispatch request, acceptance, and callback payload
- codify current execution-run activity payload
- add generation scripts for TypeScript and Python artifacts

Current status:

- initial `contracts/` directory exists in the main repo
- first draft schemas exist for dispatch, acceptance, callback, and execution-run activity payloads
- generation script exists for frontend/backend schema snapshots
- sibling `silo-forge-symphony` can also consume generated schema snapshots from the same source
- backend callback ingest already validates against the generated execution callback schema
- task and approval activity payloads now use the same schema + finalizer pattern
- next step is runtime-side callback validation and wider type adoption on top of generated artifacts

### Phase 2: backend and frontend adoption

- switch `backend` callback validation to generated types
- switch `frontend` runtime activity helpers to generated payload types
- keep compatibility shims for existing stored payload rows

### Phase 3: Symphony adoption

- replace local `MissionControlDispatch*` interfaces with generated artifacts
- remove drift between `backend` and `symphony` callback fields
- validate outgoing callback payloads against the shared schema before POST

### Phase 4: CI enforcement

- add a contract generation check
- fail CI if generated artifacts are stale
- optionally add schema compatibility tests

## Current known contract fields

These are already flowing through the system and should be preserved in the initial schema:

- `run_id`
- `run_short_id`
- `silo_slug`
- `role_slug`
- `status`
- `external_run_id`
- `workspace_path`
- `branch_name`
- `pr_url`
- `pull_request`
- `summary`
- `error_message`
- `total_tokens`
- `issue_identifier`
- `runner_kind`
- `completion_kind`
- `last_event`
- `last_message`
- `session_id`
- `turn_count`
- `duration_ms`

## Guardrails

- keep contract schemas product-centric, not tied to one runtime's internal file layout
- do not leak database-only fields into public callback contracts unless they are required
- prefer explicit version fields if payloads begin to branch
- keep generated files checked in for now; revisit later if build tooling matures

## Working note

The current repo is still the best place to incubate the contract source-of-truth.
Once the execution contract stops shifting, it can graduate into a standalone package.

## Operational note

Use `make contracts-gen` in `silo-forge` to refresh generated contract snapshots.
If a sibling checkout exists at `../symphony`, the same command also refreshes
`silo-forge-symphony/src/contracts/generated/schemas.ts`.
