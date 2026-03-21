# Silo MVP

## Purpose

Mission Control should become the control plane for creating and managing small agent silos.

This document defines the minimum architecture needed to move from the current
gateway/board/agent model to a productized silo factory without collapsing
authoring, control, and runtime concerns into one system.

## Core Rules

### Secret ownership

Mission Control must not own plaintext secrets.

It may store:

- Vault path references
- logical secret names
- env binding schemas
- secret rotation metadata

It must not store:

- API keys
- gateway tokens
- bot tokens
- rendered `.env` file contents

The current reference repo still contains values that look like plaintext
runtime secrets. Those patterns are reference-only anti-patterns and must not
carry into Mission Control product behavior.

### Plane separation

Keep three planes separate:

- Git authoring plane
- Mission Control control plane
- gateway filesystem runtime plane

This means:

- Git stores editable blueprint source
- Mission Control stores desired topology and rollout state
- runtime hosts store rendered artifacts only

### Desired vs rendered separation

Mission Control should store desired config, not host-rendered config blobs.

Rendered config is derived late from:

- blueprint version
- silo inputs
- gateway target
- secret binding map
- optional add-ons

## Minimum Service Boundaries

### `SiloService`

- silo CRUD
- archive / clone
- lifecycle status

### `BlueprintService`

- import blueprint pack
- version blueprint
- diff blueprint revisions
- publish blueprint

### `ConfigRenderer`

- render workspace docs
- render runtime config
- render Symphony config
- render collector config

### `ProvisionPlanService`

- decide what gets deployed
- decide where it goes
- order runtime apply steps

### `RuntimeApplyService`

- validate bundle against target runtime
- apply bundle
- rotate tokens
- trigger restarts when required
- verify health after apply

### `TelemetryIngestService`

- usage hub ingest
- collector push ingest
- metrics normalization

### `DriftDetectionService`

- desired vs actual comparison
- stale runtime detection
- actionable reconcile output

### `SecretBindingService`

- logical secret -> Vault path/key mapping
- runtime env var mapping
- secret contract validation

## MVP Stages

### MVP-1: Silo Registry + Provisioning

Add:

- silo records
- silo roles
- silo members
- silo blueprints
- default 4-agent silo wizard

Outcome:

- operators can create a new silo from the UI

### MVP-2: Symphony + Telemetry

Add:

- per-silo Symphony toggle
- usage hub registration
- silo health / cost / token dashboard

Outcome:

- operators can manage ongoing silo operations in one place

### MVP-3: Git-backed Blueprint + Drift Management

Add:

- Git blueprint import
- diff / preview / reconcile
- clone silo
- export silo

Outcome:

- Mission Control becomes a reusable silo factory

## Key Product Screen

The most important screen is `Silo Detail`.

Sections:

- Overview
- Roles
- Runtime
- Work
- Telemetry
- Config
- Operations

## Current Technical Direction

PicoClaw now exposes runtime surfaces suitable for Mission Control integration:

- runtime inventory
- runtime bundle validate
- runtime bundle apply
- host-env-backed secret binding resolution

That means the next Mission Control step is to formalize the desired-state side:

- blueprint contracts
- secret binding contracts
- provision targets
- default silo blueprints

## Locked Decisions

The following product decisions are now fixed for MVP implementation unless
explicitly revised later:

- `Organization` and `Silo` stay separate.
- `Gateway` remains an organization-shared asset.
- Symphony integrates against Mission Control task flows first, not Linear.
- `openclaw-agent` shifts toward blueprint-catalog responsibility.
- `symphony` is treated as an upstream-aligned execution runtime fork, not as a
  separate product center.
- Mission Control remains the product center and control plane.

## Execution Breakdown

### Stage 0: Contract Lock

Goal:

- freeze the desired-state contracts before broad implementation

Required outputs:

- `SiloCreate`, `SiloUpdate`, `SiloPreviewRead`, `SiloDetailRead`
- built-in `default-four-agent` blueprint
- secret-binding contract with Vault-path references only
- runtime bundle preview contract for PicoClaw validate/apply flows

Implementation checklist:

- keep silo persistence scoped to desired state only
- keep rendered runtime bundle generation inside silo runtime services
- reject plaintext secret ownership in Mission Control models and docs

### Stage 1: Persistence MVP

Goal:

- persist silo records and resolved role assignments

Required outputs:

- `silos` table
- `silo_roles` table
- `silo_runtime_operations` table
- `silo_runtime_operation_results` table
- silo CRUD and detail APIs

Implementation checklist:

- enforce org-scoped silo slug uniqueness
- enforce per-silo role slug uniqueness
- store desired-state preview JSON on the silo row
- keep runtime operation history append-only

### Stage 2: Provision Preview MVP

Goal:

- produce operator-visible runtime plans before any apply action

Required outputs:

- blueprint list/detail API
- silo preview API
- provision-plan preview API
- PicoClaw bundle rendering for gateway-backed roles

Implementation checklist:

- support unassigned gateways without failing preview generation
- emit warnings when optional add-ons are disabled
- skip Symphony bundle rendering for now, but preserve role visibility

### Stage 3: Runtime Validate/Apply MVP

Goal:

- allow operators to validate and apply silo runtime bundles

Required outputs:

- runtime validate API
- runtime apply API
- persisted runtime operation history in silo detail

Implementation checklist:

- resolve assigned gateway per role at apply time
- use organization-shared gateway rows as runtime targets
- store validation/apply result payloads for audit/debugging

### Stage 4: Operator UI MVP

Goal:

- expose silo create/list/detail flows in the frontend

Required outputs:

- silo list page
- create silo page
- silo detail page with roles/config/runtime sections

Implementation checklist:

- make gateway assignment editable after create
- show provision-plan warnings prominently
- show latest runtime validate/apply result in silo detail

### Stage 5: Next Milestones After MVP

After the above ships, proceed in this order:

1. add Alembic-backed production migration coverage and rollout checks
2. add richer blueprint import/versioning beyond built-ins
3. add Mission Control task-backed Symphony execution
4. add usage-hub/openclaw-smi telemetry ingestion
5. add drift detection and reconcile flows

## Task-Backed Symphony Scaffold

Mission Control now has the first task-backed execution scaffold.

Current backend shape:

- `TaskExecutionRun` stores one task-triggered execution attempt.
- `POST /boards/{board_id}/tasks/{task_id}/execution-runs` creates a queued run.
- `POST /boards/{board_id}/tasks/{task_id}/execution-runs/{run_id}/dispatch` enqueues background dispatch.
- background dispatch builds a Symphony-compatible issue contract from the Mission Control task and persists a stub acceptance.

Current dispatch semantics:

- run status moves from `queued` to `dispatching`
- Mission Control derives a normalized `issue` payload compatible with Symphony's tracker contract
- Mission Control assigns deterministic `external_run_id`, `workspace_path`, and `branch_name`
- `result_payload` stores both `dispatch_request` and `dispatch_acceptance`
- if `SYMPHONY_BRIDGE_BASE_URL` is configured, Mission Control POSTs dispatches to the bridge instead of using the stub adapter
- Symphony can report status back to `POST /api/v1/task-execution-runs/{run_id}/callbacks/symphony`

Still missing before live Symphony execution:

- richer worker event streaming beyond coarse status callbacks
- PR/status synchronization back into task state, comments, and approvals
