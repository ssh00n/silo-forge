# Fork Branding Checklist

This checklist is for the forked product transition from the upstream repository.

## Already Done In This Fork

- `LICENSE` is preserved from upstream.
- Root `NOTICE` exists and names the upstream repository and license.
- `README.md` includes a fork transition note.
- Git remotes are split into:
  - `origin` = fork
  - `upstream` = original repository

## Required To Keep

- Keep the upstream `LICENSE` file in the repository.
- Keep `NOTICE` or move to `THIRD_PARTY_NOTICES` only if you want a broader notices file later.
- Keep one explicit upstream attribution note in the root `README.md`.

## Branding Separation Rules

- Do not ship the final product brand as `OpenClaw Mission Control`.
- Do not use upstream repository naming as the primary product identity in:
  - landing copy
  - navigation labels
  - page metadata
  - screenshots
  - release notes
  - installer/bootstrap copy

## Safe Transition Sequence

1. Keep legal attribution files stable.
2. Choose the new product brand.
3. Rename visible product strings in one intentional pass.
4. Leave internal API paths and module paths unchanged unless there is a technical reason to rename them.
5. Keep `upstream` remote for future sync.

## Recommended Immediate Follow-up

1. Pick the product name to ship.
2. Update top-level README title and first paragraph.
3. Update frontend branding surfaces.
4. Update screenshots and deployment docs.
5. Re-run local E2E after the branding pass.
