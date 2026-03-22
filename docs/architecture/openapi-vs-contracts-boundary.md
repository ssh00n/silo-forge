# OpenAPI vs Contracts Boundary

This note defines which type system should be treated as authoritative in `Silo Forge`.

## Why this exists

The codebase now has two distinct generated-type families:

- OpenAPI-generated client and model types
- contracts-generated schema snapshots and typed aliases

Both are useful, but they solve different problems.
If they are mixed carelessly, drift and confusion come back quickly.

## Decision

Use:

- `OpenAPI-generated` types for request/response shapes owned by the FastAPI HTTP surface
- `contracts-generated` types for cross-service payloads that must stay stable across runtimes

Do not treat them as interchangeable by default.

## OpenAPI-generated types

Primary role:

- frontend API client typing
- request and response shapes for normal control-plane endpoints
- compatibility with the currently deployed backend HTTP surface

Examples:

- task CRUD
- board snapshot responses
- silo detail API responses
- approval API responses

These types should remain the default choice when:

- the data is strictly a backend HTTP response
- the shape is already fully defined by FastAPI/Pydantic response models
- no second runtime or service needs to consume the payload independently

## Contracts-generated types

Primary role:

- execution dispatch request payloads
- execution dispatch acceptance payloads
- execution callback payloads
- activity payloads shared across frontend/backend/runtime boundaries

Examples:

- `ExecutionDispatchRequest`
- `ExecutionDispatchAcceptance`
- `ExecutionCallbackPayload`
- `ActivityExecutionRunPayload`
- task activity payload
- approval activity payload

These types should be preferred when:

- a payload crosses repo or service boundaries
- a non-HTTP transport is involved
- frontend and backend both interpret the same payload shape
- runtime systems such as `silo-forge-symphony` must validate or emit the same shape

## Boundary rules

### Rule 1: HTTP resource models stay OpenAPI-first

If a value is primarily an API response object, keep using OpenAPI-generated typing.

Do not rewrite ordinary REST response models into contracts unless a real cross-service reuse need appears.

### Rule 2: Integration payloads stay contracts-first

If a payload is sent between:

- backend and runtime
- backend and queue worker
- backend and frontend activity surfaces
- future microservices

then it should come from `contracts/` and generated artifacts.

### Rule 3: Wrappers remain local

Service-local wrappers and finalizers are still allowed and expected.

Examples:

- `backend/app/contracts/execution.py`
- `backend/app/contracts/activity.py`

These wrappers:

- validate against generated schemas
- normalize optional/null fields
- adapt to service-specific runtime needs

The wrapper is not the source-of-truth.
The schema is.

### Rule 4: Do not import runtime types across repos

Never make `frontend`, `backend`, or `silo-forge-symphony` depend on one another's internal runtime types.

Only consume:

- committed generated artifacts
- shared schema-derived aliases

## Current practical split

### Keep OpenAPI-generated for

- API client calls in `frontend/src/api/generated`
- resource reads like boards, tasks, silos, approvals, agents
- normal backend request/response DTOs

### Keep contracts-generated for

- execution dispatch/callback payloads
- runtime activity payloads
- task/approval activity payloads
- future queue/job payloads

## Expansion policy

Do not move every model into contracts.

Only promote a shape into `contracts/` when at least one is true:

- two services need it
- one service emits it and another interprets it independently
- drift risk has already appeared
- a queue/event/callback boundary exists

## Current recommendation

Continue using the current pattern:

- root `contracts/` as the source-of-truth
- service-local generated artifacts in:
  - `frontend/src/contracts`
  - `backend/app/contracts`
  - `silo-forge-symphony/src/contracts`
- thin wrappers/finalizers at service boundaries

This is the right tradeoff for the current stage of the system.
