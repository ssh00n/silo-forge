# Product Transition Pre-E2E

This document locks the product direction, naming options, attribution policy, and the final preparation checklist before local E2E.

## Current Product State

The current working tree is no longer just the upstream Mission Control UI.
It now contains the beginnings of a control plane for creating and operating small OpenClaw silos.

Implemented or materially extended in this branch:

- `Silo` domain and runtime operation history
- task-backed Symphony execution run lifecycle
- runtime metrics on dashboard
- payload-first activity rendering across dashboard, activity feed, and board live feed
- board live feed category filters plus realtime generic activity streaming
- dashboard recent-activity category filters plus realtime activity streaming
- structured activity payloads for task, approval, gateway, agent lifecycle, and silo runtime events

## Product Boundary

Locked direction:

- `Mission Control`-derived repo becomes the main product control plane
- `openclaw-agent` becomes blueprint/source catalog
- `symphony` stays an upstream-aligned execution runtime integration surface

The product is now closer to:

- silo factory
- runtime control plane
- governance and approvals console
- operations visibility layer

and less like:

- generic project management UI
- standalone runtime/orchestrator product

## Naming Direction

The upstream name `OpenClaw Mission Control` should not remain the shipped product brand.

Selection criteria:

- should read as an operator/control-plane product
- should fit silo creation and runtime operations
- should not depend on `OpenClaw` branding
- should still feel compatible with future blueprint/runtime products

Recommended candidates:

1. `Silo Forge`
   - strongest alignment with “create and manage small agent silos”
   - good fit for provisioning, runtime apply, and blueprint-driven workflows
2. `Run Foundry`
   - emphasizes execution/runtime operations
   - slightly broader, less explicit about silo management
3. `Control Forge`
   - control-plane oriented
   - more generic, less product-specific
4. `Nest Control`
   - memorable, but slightly softer and less enterprise/operator-facing
5. `Fleet Foundry`
   - strong for multi-silo future, but weaker for the initial “small silo” story

Current recommendation:

- choose `Silo Forge` unless later user research strongly favors a more general control-plane name

Working rename policy before the actual rename:

- keep repo code paths stable for now
- add attribution and transition docs first
- rename product strings in one intentional pass after local E2E confidence is high

## Attribution And Fork Policy

Practical safe path:

- fork into your own GitHub account
- preserve `LICENSE`
- keep a root-level `NOTICE` or `THIRD_PARTY_NOTICES`
- explicitly separate product brand from upstream project name
- keep one line in `README` that acknowledges upstream origin during transition

Current repo actions:

- `LICENSE` preserved
- `NOTICE` added
- `README` now points to attribution + transition docs

## Planned Branding Pass

When the new name is chosen, replace these surfaces in one pass:

- root `README.md` title and first paragraph
- frontend nav/sidebar labels
- page titles and metadata
- screenshots and marketing copy
- docs headings that still assume the upstream brand
- Docker/bootstrap text that references `openclaw-mission-control`

Do not change yet:

- package/module paths unless necessary
- migration names
- backend API path prefixes

## Pre-E2E Preparation Checklist

Before running browser E2E:

1. Confirm local auth mode works end-to-end.
2. Confirm one board and one gateway are available.
3. Confirm one silo exists with at least one gateway-backed role.
4. Confirm `/api/v1/activity/stream` works and dashboard live activity updates.
5. Confirm board live feed receives runtime/gateway activity in realtime.
6. Confirm task execution run create, dispatch, callback, and retry still work.
7. Confirm runtime metrics and board/task run panels stay consistent.

## Immediate Next Step

After this document is in place, the next step is not more architecture work.
The next step is local E2E execution:

- dashboard recent activity realtime
- board live feed realtime
- silo runtime validate/apply
- task-backed Symphony run loop
- retry/review transitions
