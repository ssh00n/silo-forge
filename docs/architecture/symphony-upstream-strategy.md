# Symphony Upstream Strategy

## Decision

The product center is `openclaw-mission-control`.

The repository roles are fixed as:

- `openclaw-mission-control`: product control plane
- `openclaw-agent`: blueprint and source catalog
- `symphony`: upstream-aligned execution runtime fork/workspace

The extracted `symphony` repository is not a new independent product.
It exists to:

- track `openai/symphony` as the execution-runtime reference
- carry the minimum integration delta required for Mission Control
- keep runtime ownership separate from blueprint ownership

## Why This Direction

`openai/symphony` already exists as the public execution-runtime reference.

That means building and maintaining a second long-lived independent Symphony-like
runtime would create unnecessary product overlap.

Our differentiated product value is elsewhere:

- silo creation and lifecycle
- approvals and governance
- gateway-aware provisioning
- telemetry and operational visibility
- blueprint import and rollout

Those belong in Mission Control, not in a custom runtime rewrite.

## Ownership Table

| Area | Mission Control | openclaw-agent | symphony fork |
| --- | --- | --- | --- |
| Silo registry | Owns | Reference only | Does not own |
| Task lifecycle | Owns | Does not own | Reports runtime status only |
| Approvals / policy | Owns | Does not own | Does not own |
| Gateway provisioning | Owns | Reference contracts only | Does not own |
| Blueprint catalog | Imports and renders | Owns | Consumes rendered outputs only |
| Role packs / TEAM / SOUL | Does not author | Owns | Consumes rendered outputs only |
| Runtime execution | Dispatches and observes | Does not own | Owns |
| Tracker/runtime worker loop | Does not own | Does not own | Owns |
| Mission Control bridge | Owns API contract and callback ingest | Owns schemas/docs only | Owns runtime implementation |
| Telemetry aggregation | Owns | Reference config only | Emits runtime data only |

## Upstream Strategy

### Upstream source

- `https://github.com/openai/symphony`

### Local runtime role

The local `symphony` repository should be treated as:

- an upstream-aligned fork or integration workspace
- a place for the smallest viable Mission Control-specific runtime delta

It should not drift into:

- a separate orchestration product strategy
- a blueprint/source catalog
- a control-plane clone

## Keep vs Customize

| Category | Strategy |
| --- | --- |
| Core orchestrator model | Follow upstream where possible |
| Workspace semantics | Preserve and align with upstream expectations |
| Runner abstractions | Follow upstream unless Mission Control integration requires small adaptations |
| Tracker abstractions | Prefer upstream model; add Mission Control dispatch path as additive integration |
| HTTP bridge for Mission Control | Custom fork delta |
| Mission Control callback sender | Custom fork delta |
| Runtime deploy wrappers | Custom if needed, but keep isolated from product logic |
| Silo/approval/policy logic | Never move into runtime |

## Task Flow Reset

The execution path is now:

1. `openclaw-agent` defines blueprint contracts and authored runtime expectations
2. Mission Control imports blueprint metadata and renders desired state
3. Mission Control provisions gateway/runtime topology for a silo
4. Mission Control creates task execution runs from board tasks
5. Mission Control dispatches work into the Symphony fork
6. Symphony executes the run and sends callbacks
7. Mission Control updates task state, activity, approvals, and telemetry views

This keeps authored assets, control-plane policy, and runtime execution separate.

## Implementation Boundaries

### Mission Control should implement

- task-backed execution-run lifecycle
- dispatch request construction
- callback ingest
- silo/runtime assignment UI
- approval/task synchronization after runtime completion
- telemetry ingestion and runtime health views

### openclaw-agent should implement

- blueprint schemas
- default silo packs
- authored workflow examples
- runtime contract documents
- deployment/reference notes

### symphony fork should implement

- Mission Control dispatch intake
- callback sending
- runtime status updates
- worker launch and reconciliation
- upstream sync and conflict handling

## Immediate Roadmap Shift

Do next:

1. stop describing the extracted `symphony` repo as a new standalone product
2. describe it as an upstream-aligned runtime fork
3. keep Mission Control task execution work moving
4. keep openclaw-agent focused on contracts and blueprint surfaces
5. keep runtime customizations narrowly scoped and documented as fork deltas

## Fork Delta Rule

Every custom change in the `symphony` repo should answer one question:

`Is this required to integrate Symphony with Mission Control?`

If the answer is no, prefer upstream alignment instead of local divergence.
