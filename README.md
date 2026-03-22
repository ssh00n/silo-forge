# Silo Forge

[![CI](https://github.com/ssh00n/silo-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/ssh00n/silo-forge/actions/workflows/ci.yml)

Forked from `abhi1693/openclaw-mission-control`. This repository keeps the upstream MIT license and attribution. See [NOTICE](./NOTICE).

Silo Forge is a silo-centric control plane for operating small agent organizations.
Its core job is not just to create silos, but to help an operator:

- create and configure silos
- assign runtime-capable work to the right silo
- observe health, workload, and progress
- intervene when runs fail, block, or need approval

This repository is the product center and control plane.
The execution runtime lives in the sibling repository [`silo-forge-symphony`](https://github.com/ssh00n/silo-forge-symphony).

## What The Product Does

Silo Forge is designed around one operational loop:

1. define or materialize a silo
2. give work to that silo
3. watch runtime progress
4. respond to failures, approvals, and blocked work
5. keep the organization explainable through activity and contracts

The current product surface is centered on:

- `Dashboard`
  - operator-first overview of silo health, active assignments, runtime pressure, approvals, and telemetry
- `Silos`
  - silo inventory with health and workload posture
- `Silo detail`
  - configuration, runtime posture, current work, and operator next actions
- `Boards / Tasks`
  - task-centric workflow, approvals, comments, and runtime dispatch
- `Activity`
  - timeline of task, approval, runtime, queue, webhook, and silo events

`Silo Requests` exists, but it is a secondary planning queue. The core UX is silo operations.

## Repository Roles

### This repo: `silo-forge`

This repository owns:

- the web UI
- the FastAPI control plane
- the Postgres-backed system of record
- operator workflows
- activity and telemetry surfaces
- contract source-of-truth for cross-service execution flows

### Sibling repo: `silo-forge-symphony`

The sibling runtime repository owns:

- accepting dispatch requests from the control plane
- preparing workspace and runtime execution
- running Symphony turns
- reporting execution callbacks back into Silo Forge

The two repositories are intentionally separate:

- `silo-forge` is the product and control plane
- `silo-forge-symphony` is the execution runtime integration layer

## Architecture

### High-level components

- `frontend/`
  - Next.js operator UI
- `backend/`
  - FastAPI API, persistence, orchestration, metrics, activity, approvals
- `Postgres`
  - source of truth for silos, tasks, runs, approvals, activity, telemetry snapshots
- `Redis + worker`
  - dispatch queue and async execution handoff
- `silo-forge-symphony`
  - runtime bridge and callback emitter
- `contracts/`
  - source-of-truth schemas for execution, activity, queue, and telemetry boundaries

### Runtime flow

The most important runtime path is:

1. an operator opens a task on a board
2. Silo Forge evaluates task demand and available silos
3. the operator dispatches a run to a selected silo
4. backend creates a `TaskExecutionRun`
5. backend enqueues a dispatch job to Redis
6. worker consumes the job and sends a dispatch request to Symphony
7. Symphony runs the work and emits callbacks
8. backend updates run state and activity
9. UI surfaces refresh:
   - task detail
   - dashboard
   - board live feed
   - activity feed
   - silo workload views

### Core data model

The most important product objects are:

- `Organization`
  - top-level boundary for users, boards, silos, and governance
- `Silo`
  - the main operating unit in the product
- `SiloRole`
  - role definition inside a silo, such as gateway-backed or symphony-backed roles
- `Board`
  - task workspace and operator collaboration context
- `Task`
  - work item that can produce approvals, activity, and runtime runs
- `TaskExecutionRun`
  - concrete runtime execution attempt attached to a task and silo
- `Approval`
  - governance gate for risky or escalated work
- `ActivityEvent`
  - timeline record for product-visible events

## How Frontend, Backend, And Symphony Work Together

### Frontend

The frontend is not a thin shell. It contains shared operator policy and presentation logic for silo-centric UX.

Important frontend layers:

- `frontend/src/app/`
  - route-level pages such as dashboard, boards, silos, activity
- `frontend/src/lib/silo-ops/`
  - centralized silo operator policy
  - health taxonomy
  - task demand classification
  - dispatch candidate scoring
  - shared view-models
  - presentation helpers
- `frontend/src/lib/runtime-runs.ts`
  - runtime operator state, guidance, and parsing
- `frontend/src/lib/activity-events.ts`
  - activity-feed payload interpretation

The frontend currently treats these as core shared vocabularies:

- silo health
  - `Healthy`
  - `Busy`
  - `Degraded`
  - `Blocked`
  - `Needs setup`
- task demand
  - approval pressure
  - blocked dependency pressure
  - active follow-up
  - standard demand
- dispatch continuity
  - current silo
  - last used silo
  - alternative silo

### Backend

The backend owns authoritative state and orchestration.

Important backend areas:

- `backend/app/api/`
  - HTTP API
- `backend/app/services/silos/`
  - silo creation, preview, detail, runtime validate/apply, provision plan
- `backend/app/services/task_execution_runs.py`
  - create, retry, cancel, acknowledge, escalate, update runtime runs
- `backend/app/services/task_execution_dispatch.py`
  - dispatch payload generation for Symphony
- `backend/app/services/task_execution_worker.py`
  - async dispatch execution
- `backend/app/api/task_execution_callbacks.py`
  - callback ingestion from Symphony
- `backend/app/api/metrics.py`
  - dashboard-oriented read models
- `backend/app/contracts/`
  - runtime validation/finalization at service boundaries

The backend does not try to duplicate every frontend policy.
Instead it exposes minimal read models where centralization is valuable, such as:

- `SiloDetailRead.operational_summary`
- dashboard runtime metrics
- telemetry snapshots

That split is intentional:

- backend owns durable state and minimal operational summaries
- frontend owns shared operator shaping through `silo-ops`

### Symphony

`silo-forge-symphony` is the runtime execution side.

It receives dispatch requests from Silo Forge and returns callback updates such as:

- queued
- dispatching
- running
- succeeded
- failed
- blocked
- cancelled

It also sends richer runtime metadata used by the control plane, including fields such as:

- `completion_kind`
- `failure_reason`
- `block_reason`
- `cancel_reason`
- `stall_reason`
- `last_event`
- `last_message`
- `session_id`
- `turn_count`
- `duration_ms`

This is what makes the operator surfaces in Silo Forge more than a generic task board.

## Contracts And Service Boundaries

Cross-service boundaries are defined in [contracts/](./contracts/).

These schemas cover:

- execution dispatch request / acceptance / callback
- activity payloads
- queue payloads and queue envelope
- telemetry payloads

Generated artifacts are consumed separately by each service:

- frontend
  - `frontend/src/contracts/generated/`
- backend
  - `backend/app/contracts/generated_schemas.py`
- sibling runtime
  - `silo-forge-symphony/src/contracts/generated/`

Refresh them with:

```bash
make contracts-gen
```

Check for drift with:

```bash
make contracts-check
```

This keeps the source-of-truth centralized without making services import each other directly.

## Local Development

### Fastest path

```bash
make setup
make local-dev-up
```

This bootstraps the local stack used for end-to-end control-plane work:

- Postgres
- Redis
- backend
- frontend
- worker
- optional local Symphony bridge when `../symphony` exists

Useful commands:

```bash
make local-dev-status
make local-dev-down
make local-dev-reset
```

Preflight:

```bash
bash scripts/local_e2e_preflight.sh
```

Seed demo data:

```bash
cd backend && ./.venv/bin/python scripts/seed_demo.py
```

### Manual loop

Backend:

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

## Key Workflows

### 1. Silo operations

- create a silo
- assign gateway-backed roles
- validate runtime
- apply runtime
- observe silo health and current work
- use `What next` guidance in silo detail

### 2. Task-to-silo execution

- open a task
- inspect task demand
- inspect current silo or last used silo
- continue on the same silo when continuity matters
- choose an alternative silo when health or pressure requires it
- dispatch a runtime run

### 3. Runtime operator flow

For each execution run the operator can:

- retry
- cancel
- acknowledge
- escalate

Escalation feeds into approvals and task review flows, and the outcome is reflected back in runtime guidance.

### 4. Activity and telemetry

The operator can inspect:

- activity timeline
- dashboard recent activity
- board live feed
- queue worker telemetry
- webhook delivery telemetry
- runtime state transitions

## Current Product Direction

The product is currently being shaped around this principle:

- core UX is silo operations
- secondary UX is planning and capacity requests

That means the most important surfaces are:

- `Dashboard`
- `Silos`
- `Silo detail`
- `Board task detail`

And the main questions the product should answer are:

- which silo is healthy?
- which silo is busy, degraded, or blocked?
- which silo is currently carrying a task?
- should the operator continue on the same silo or switch?
- what should the operator do next?

## Project Layout

```text
backend/                 FastAPI control plane
backend/app/api/         HTTP routes
backend/app/services/    orchestration and read models
backend/app/contracts/   backend-side contract validation/finalization
backend/tests/           pytest suite

frontend/                Next.js operator UI
frontend/src/app/        route surfaces
frontend/src/lib/        client-side shared logic
frontend/src/lib/silo-ops/
                         centralized silo operator policy and view-models
frontend/src/api/generated/
                         generated API client

contracts/               cross-service schema source-of-truth
docs/                    architecture, testing, and operations notes
scripts/                 local dev and generation utilities
```

## Testing

Closest CI-parity run:

```bash
make check
```

Common targeted commands:

```bash
make contracts-check
cd backend && ./.venv/bin/python -m pytest
cd frontend && npm run lint
cd frontend && npm run test
```

## Related Documentation

- [Architecture index](./docs/architecture/README.md)
- [Silo Control Plane Roadmap](./docs/architecture/silo-control-plane-roadmap.md)
- [Silo Ops Refactor Plan](./docs/architecture/silo-ops-refactor-plan.md)
- [OpenAPI vs Contracts Boundary](./docs/architecture/openapi-vs-contracts-boundary.md)
- [Local dev stack](./docs/testing/local-dev-stack.md)
- [Local E2E silo runtime flow](./docs/testing/local-e2e-silo-runtime.md)

## License

MIT. See [LICENSE](./LICENSE).
