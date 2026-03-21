#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_ENV="${ROOT_DIR}/.env"
BACKEND_ENV="${ROOT_DIR}/backend/.env"
FRONTEND_ENV="${ROOT_DIR}/frontend/.env"
ROOT_ENV_EXAMPLE="${ROOT_DIR}/.env.example"
BACKEND_ENV_EXAMPLE="${ROOT_DIR}/backend/.env.example"
FRONTEND_ENV_EXAMPLE="${ROOT_DIR}/frontend/.env.example"

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"

print_section() {
  printf '\n== %s ==\n' "$1"
}

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

warn() {
  printf 'WARN: %s\n' "$1"
}

read_env_value() {
  local file="$1"
  local key="$2"
  local line
  line="$(grep -E "^${key}=" "$file" | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    return 1
  fi
  printf '%s' "${line#*=}"
}

first_existing_file() {
  local file
  for file in "$@"; do
    if [[ -f "$file" ]]; then
      printf '%s' "$file"
      return 0
    fi
  done
  return 1
}

check_token_length() {
  local token="$1"
  local label="$2"
  if [[ "${#token}" -lt 50 ]]; then
    fail "${label} must be at least 50 characters"
  fi
}

http_ok() {
  local url="$1"
  curl -fsS "$url" >/dev/null
}

print_section "Env files"
if [[ -f "$ROOT_ENV" ]]; then
  printf 'Found %s\n' "$ROOT_ENV"
else
  warn "Root .env not found; using backend/.env and frontend/.env only"
fi

backend_env_source="$(first_existing_file "$BACKEND_ENV" "$ROOT_ENV" "$BACKEND_ENV_EXAMPLE" "$ROOT_ENV_EXAMPLE" || true)"
frontend_env_source="$(first_existing_file "$FRONTEND_ENV" "$ROOT_ENV" "$FRONTEND_ENV_EXAMPLE" "$ROOT_ENV_EXAMPLE" || true)"

if [[ -n "$backend_env_source" ]]; then
  printf 'Backend env source: %s\n' "$backend_env_source"
else
  warn "No backend env file found; health checks will be used instead"
fi
if [[ -n "$frontend_env_source" ]]; then
  printf 'Frontend env source: %s\n' "$frontend_env_source"
else
  warn "No frontend env file found; health checks will be used instead"
fi

print_section "Auth config"
backend_auth_mode=""
frontend_auth_mode=""
if [[ -n "$backend_env_source" ]]; then
  backend_auth_mode="$(read_env_value "$backend_env_source" "AUTH_MODE" || true)"
fi
if [[ -n "$frontend_env_source" ]]; then
  frontend_auth_mode="$(read_env_value "$frontend_env_source" "NEXT_PUBLIC_AUTH_MODE" || true)"
fi
if [[ -n "$backend_auth_mode" ]]; then
  [[ "$backend_auth_mode" == "local" ]] || fail "backend AUTH_MODE must be local for local E2E"
  printf 'Backend AUTH_MODE=%s\n' "$backend_auth_mode"
else
  warn "Could not resolve backend AUTH_MODE from env files"
fi
if [[ -n "$frontend_auth_mode" ]]; then
  [[ "$frontend_auth_mode" == "local" ]] || fail "frontend NEXT_PUBLIC_AUTH_MODE must be local for local E2E"
  printf 'Frontend NEXT_PUBLIC_AUTH_MODE=%s\n' "$frontend_auth_mode"
else
  warn "Could not resolve frontend NEXT_PUBLIC_AUTH_MODE from env files"
fi

backend_token=""
if [[ -n "$backend_env_source" ]]; then
  backend_token="$(read_env_value "$backend_env_source" "LOCAL_AUTH_TOKEN" || true)"
fi
if [[ -n "$backend_token" ]]; then
  check_token_length "$backend_token" "LOCAL_AUTH_TOKEN"
  printf 'LOCAL_AUTH_TOKEN length=%s\n' "${#backend_token}"
else
  warn "Could not resolve LOCAL_AUTH_TOKEN from env files"
fi

frontend_api_url=""
if [[ -n "$frontend_env_source" ]]; then
  frontend_api_url="$(read_env_value "$frontend_env_source" "NEXT_PUBLIC_API_URL" || true)"
fi
if [[ -n "$frontend_api_url" ]]; then
  printf 'NEXT_PUBLIC_API_URL=%s\n' "$frontend_api_url"
else
  warn "Could not resolve NEXT_PUBLIC_API_URL from env files"
fi

print_section "HTTP health"
http_ok "${BACKEND_URL}/healthz" || fail "Backend health check failed at ${BACKEND_URL}/healthz"
printf 'Backend healthy: %s/healthz\n' "$BACKEND_URL"
http_ok "${FRONTEND_URL}" || fail "Frontend health check failed at ${FRONTEND_URL}"
printf 'Frontend reachable: %s\n' "$FRONTEND_URL"

print_section "Recommended seed command"
printf 'If you need a minimal local board/gateway/user dataset, run:\n'
printf '  cd backend && uv run python scripts/seed_demo.py\n'

print_section "Next step"
printf 'Preflight passed. Continue with docs/testing/local-e2e-silo-runtime.md\n'
