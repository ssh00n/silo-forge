#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

python3 scripts/generate_contract_artifacts.py

paths=(
  backend/app/contracts/generated_schemas.py
  frontend/src/contracts/generated/schemas.ts
)

if [ -f ../symphony/src/contracts/generated/schemas.ts ]; then
  if ! git -C ../symphony diff --exit-code -- src/contracts/generated/schemas.ts; then
    echo "Sibling Symphony contract artifacts are stale. Run 'make contracts-gen' and commit the results."
    exit 1
  fi
fi

if ! git diff --exit-code -- "${paths[@]}"
then
  echo "Contract artifacts are stale. Run 'make contracts-gen' and commit the results."
  exit 1
fi

echo "Contract artifacts are up to date."
