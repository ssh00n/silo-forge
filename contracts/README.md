# Contracts

This directory is the source-of-truth incubation point for cross-service contracts used by `Silo Forge`.

Current scope:

- Symphony dispatch request
- Symphony dispatch acceptance
- Symphony callback payload
- execution-run activity payload rendered by frontend surfaces

Working rules:

- hand-maintained interfaces in each service may exist temporarily
- new fields should be added here first once the shape stabilizes
- generated artifacts should eventually replace duplicated service-local types
- contracts should stay product-centric and avoid leaking service-internal implementation details

Initial layout:

```text
contracts/
  execution/
    dispatch.request.schema.json
    dispatch.acceptance.schema.json
    callback.payload.schema.json
  activity/
    execution-run.payload.schema.json
```

Planned next step:

- add generation scripts for TypeScript and Python artifacts
- adopt generated types in backend, frontend, and `silo-forge-symphony`
