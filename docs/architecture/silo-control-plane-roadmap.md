# Silo Control Plane Roadmap

This document reframes `Silo Forge` around the actual product goal:

- let operators define and run small agent silos
- spawn and manage agents inside those silos
- observe, govern, retry, and evolve those silos through one control plane

`Silo` is now the primary product noun.
Under the hood, a silo may still collapse to one agent or expand to a coordinated sub-organization.

## Product Goal

The target product is not just a runtime dashboard.
It is a control plane for:

- defining operator-owned organizational units
- attaching runtimes, gateways, and policies to those silos
- spawning agents into those silos
- observing execution, failures, retries, and approvals
- managing the full lifecycle of those agents over time

In other words:

- `Silo Forge` should become the operating system for small agent organizations

## Current State

The current product has strong foundations in four areas.

### 1. Runtime Control Plane

Implemented:

- task-backed execution runs
- dispatch, retry, callback, and runtime metrics
- local E2E with both stub and real Symphony bridge flow
- dashboard, board, and task-level runtime visibility

Assessment:

- strong foundation
- not yet a complete operator workflow product

### 2. Silo Runtime Operations

Implemented:

- silo CRUD and detail pages
- runtime validate/apply flow
- runtime operation history
- runtime activity propagation into feeds

Assessment:

- good first deployment primitive
- still too runtime-centric and not yet an organization-management model

### 3. Cross-Service Contracts

Implemented:

- root `contracts/` as source-of-truth
- generated artifacts for frontend, backend, and `silo-forge-symphony`
- execution, activity, queue, and telemetry contracts
- stale checks in local tooling and CI

Assessment:

- strong architectural discipline
- ready to support more product surfaces

### 4. Operator Visibility

Implemented:

- activity feeds with structured payload rendering
- dashboard telemetry cards
- board and task telemetry summaries
- drill-down links between metrics and activity surfaces

Assessment:

- strong observability baseline
- still biased toward debugging systems, not yet managing silos as first-class product objects

## What Is Still Missing

The biggest gaps are no longer low-level runtime plumbing.
The gaps are now product-level operating concepts.

### A. Silo Operating Model

Today:

- `silo` is the real operator-facing unit

Needed:

- a clearer model for how a silo can represent one agent or a small coordinated team
- explicit desired-state and lifecycle flows around that silo

Working direction:

- keep `silo` as the primary UX vocabulary
- use lower-level runtime terms like `pod` or container only for infrastructure surfaces
- avoid premature generic abstractions until spawn/manage flows are clearer

### B. Silo Spawn And Management

Today:

- runtime execution is task-backed
- agents are visible through gateway and lifecycle events

Needed:

- explicit spawn workflow
- explicit mapping between a silo and its agents
- operator controls for start, stop, retry, replace, wake, and inspect
- persistent agent inventory at the silo and organization level

### C. Runtime Operator Flow

Today:

- success path is proven
- retries exist
- telemetry exists

Needed:

- clearer failure taxonomy
- actionable remediation UI
- timeout/cancel/blocked handling as first-class operator actions
- stronger linking between runtime state, approvals, tasks, and feed actions

### D. Multi-Silo Organization Operations

Today:

- strong board and task context
- good per-run visibility

Needed:

- organization-level view of silos and agents
- filtering by silo, runtime, gateway, health, and failure state
- compare silos and understand which ones need intervention

## Strategic Priorities

The next roadmap should be driven by product value, not by abstract architecture purity.

### Priority 1. Complete The Runtime Operator Loop

Why first:

- this is the shortest path to “operators can trust the system”
- the foundation already exists
- runtime success/failure handling determines whether the product feels real

Must include:

- failure taxonomy
- timeout/cancel/blocked semantics
- retry and remediation surfaces
- tighter activity/task/approval linkage

### Priority 2. Turn Silo Into A Real Operating Unit

Why second:

- once runtime operation is trustworthy, the next value is managing the unit itself

Must include:

- runtime apply status as a stronger state model
- role/gateway assignment health
- visible silo inventory and health
- ability to understand which agents belong to which silo

### Priority 3. Add Silo Spawn And Agent Management

Why third:

- this is the direct expression of the product goal
- it should land on top of stable runtime/operator primitives

Must include:

- spawn agent-oriented silos
- agent inventory page or panel
- lifecycle controls and status
- operator drill-down into current and past runs

### Priority 4. Organization-Level Fleet Operations

Must include:

- organization-wide silo and agent views
- health rollups
- failure queues
- governance and audit surfaces

### Priority 5. Branding And Product Narrative Completion

Must include:

- second-pass `Silo Forge` product wording cleanup
- docs and empty-state cleanup
- product vocabulary that stays anchored on `silo` while leaving room for future runtime shapes

## Recommended Execution Waves

### Wave 1. Runtime Operator Flow

Target outcome:

- an operator can reliably understand what happened to a run and what to do next

Concrete scope:

- classify execution failures and blocked states
- expose retry/cancel/remediate actions consistently
- connect runtime failures to task status and approvals more explicitly
- improve callback metadata handling in feed surfaces

### Wave 2. Silo Health And Inventory

Target outcome:

- an operator can see whether a silo is valid, applied, healthy, and ready to spawn agents

Concrete scope:

- strengthen silo runtime status model
- expose assignment health and apply history
- add organization-level silo listing improvements

### Wave 3. Silo Spawn And Agent Lifecycle

Target outcome:

- an operator can create and manage silo-contained agents from the control plane

Concrete scope:

- spawn flow
- agent inventory
- lifecycle actions
- links to runtime history and telemetry

## Guardrails

- keep `contracts/` discipline in place
- do not rename storage/API primitives just to chase vocabulary
- do not introduce a separate spawn service until spawn semantics are real
- prefer product-level workflows over more raw telemetry widgets

## Immediate Next Step

The next implementation branch should focus on:

- `runtime operator flow`

That branch should answer:

- when a run fails, blocks, stalls, or times out, what exactly does the operator do next?
