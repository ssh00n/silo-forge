# Branding Rename Strategy

This document describes how to rename the fork into the product brand without breaking the current control-plane implementation.

## Recommended Product Name

Current recommendation: `Silo Forge`

Reason:

- aligned with the silo factory direction
- fits runtime provisioning and operator workflows
- avoids dependence on upstream `OpenClaw` branding

## Rename Scope

Rename now:

- root `README.md` title
- marketing copy and first-paragraph language
- frontend visible brand text
- page metadata and app shell labels
- docs headings that are product-facing

Rename later, only if necessary:

- repository name
- package names
- backend module paths
- API route prefixes
- migration filenames

## Phase Plan

### Phase 1: Visible Product Branding

- change visible brand strings to `Silo Forge`
- keep upstream attribution note in `README.md`
- keep `LICENSE` and `NOTICE` untouched

### Phase 2: Operator UX Consistency

- align dashboard/sidebar/landing terminology
- replace remaining `Mission Control` product references in frontend copy
- leave technical docs alone if they refer to upstream concepts that still matter

Status:

- visible app shell branding is updated
- gateway/settings/loading surfaces are updated
- remaining technical references are mostly internal docs, backend names, and generated API comments

### Phase 3: Repo And Packaging Cleanup

- consider repo rename only after product direction is stable
- consider additional notices file if multiple third-party attributions accumulate

## High-Signal Surfaces To Rename First

- [README.md](/Users/shinseunghun/Documents/openclaw-mission-control/README.md)
- [frontend/src/app/layout.tsx](/Users/shinseunghun/Documents/openclaw-mission-control/frontend/src/app/layout.tsx)
- [frontend/src/components/organisms/LandingHero.tsx](/Users/shinseunghun/Documents/openclaw-mission-control/frontend/src/components/organisms/LandingHero.tsx)
- [frontend/src/components/molecules/HeroCopy.tsx](/Users/shinseunghun/Documents/openclaw-mission-control/frontend/src/components/molecules/HeroCopy.tsx)
- [frontend/src/components/templates/LandingShell.tsx](/Users/shinseunghun/Documents/openclaw-mission-control/frontend/src/components/templates/LandingShell.tsx)
- [frontend/src/components/organisms/LocalAuthLogin.tsx](/Users/shinseunghun/Documents/openclaw-mission-control/frontend/src/components/organisms/LocalAuthLogin.tsx)

## Guardrails

- keep legal attribution explicit
- do not remove upstream license text
- avoid broad mechanical rename across internal code unless it improves maintainability
- prefer a deliberate branding pass over piecemeal copy edits

## Current status

Completed in the visible product surfaces:

- landing, auth, onboarding, invite, app shell
- dashboard and board operator flows
- gateway create/edit/list copy
- loading and account settings copy

Intentionally left for later:

- generated API comments such as `Mission Control API`
- backend module names and package identifiers
- upstream-facing technical architecture documents that still describe historical context
