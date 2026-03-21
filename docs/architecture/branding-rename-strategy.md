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
