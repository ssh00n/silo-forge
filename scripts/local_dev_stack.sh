#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${ROOT_DIR}/.tmp/local-dev"
PID_DIR="${RUNTIME_DIR}/pids"
LOG_DIR="${RUNTIME_DIR}/logs"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-mc-local-postgres}"
POSTGRES_VOLUME="${POSTGRES_VOLUME:-mc_local_postgres_data}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:16-alpine}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-mission_control}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"

REDIS_CONTAINER="${REDIS_CONTAINER:-mc-local-redis}"
REDIS_IMAGE="${REDIS_IMAGE:-redis:7-alpine}"
REDIS_PORT="${REDIS_PORT:-6379}"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
SYMPHONY_PORT="${SYMPHONY_PORT:-8787}"
SYMPHONY_DIR="${SYMPHONY_DIR:-${ROOT_DIR}/../symphony}"
SYMPHONY_ENABLE="${SYMPHONY_ENABLE:-auto}"
SYMPHONY_BRIDGE_TOKEN="${SYMPHONY_BRIDGE_TOKEN:-local-symphony-bridge-token}"
SYMPHONY_CALLBACK_TOKEN="${SYMPHONY_CALLBACK_TOKEN:-local-symphony-callback-token}"
SYMPHONY_WORKFLOW_FILE="${RUNTIME_DIR}/symphony/WORKFLOW.local.md"

BACKEND_PID_FILE="${PID_DIR}/backend.pid"
FRONTEND_PID_FILE="${PID_DIR}/frontend.pid"
WORKER_PID_FILE="${PID_DIR}/worker.pid"
SYMPHONY_PID_FILE="${PID_DIR}/symphony.pid"

BACKEND_LOG_FILE="${LOG_DIR}/backend.log"
FRONTEND_LOG_FILE="${LOG_DIR}/frontend.log"
WORKER_LOG_FILE="${LOG_DIR}/worker.log"
SYMPHONY_LOG_FILE="${LOG_DIR}/symphony.log"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/local_dev_stack.sh up
  bash scripts/local_dev_stack.sh status
  bash scripts/local_dev_stack.sh down
  bash scripts/local_dev_stack.sh reset

Actions:
  up      Ensure local Postgres/Redis exist, then start backend/frontend/worker and optional symphony bridge.
  status  Show container, process, and HTTP health status.
  down    Stop backend/frontend/worker and stop Docker services.
  reset   Down + remove Redis container + Postgres container/volume for a clean slate.
EOF
}

print_section() {
  printf '\n== %s ==\n' "$1"
}

print_log_tail() {
  local label="$1"
  local log_file="$2"
  if [[ -f "$log_file" ]]; then
    print_section "${label} log tail"
    tail -n 80 "$log_file" || true
  fi
}

ensure_runtime_dirs() {
  mkdir -p "$PID_DIR" "$LOG_DIR"
  mkdir -p "$(dirname "$SYMPHONY_WORKFLOW_FILE")"
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

require_command() {
  local name="$1"
  if ! command_exists "$name"; then
    printf 'ERROR: required command not found: %s\n' "$name" >&2
    exit 1
  fi
}

is_pid_running() {
  local pid="$1"
  kill -0 "$pid" >/dev/null 2>&1
}

read_pid() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  printf '%s' "$pid"
}

clear_pid_file_if_stale() {
  local pid_file="$1"
  local pid
  pid="$(read_pid "$pid_file" || true)"
  if [[ -n "$pid" ]] && ! is_pid_running "$pid"; then
    rm -f "$pid_file"
  fi
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-40}"
  local i
  for i in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      printf '%s ready: %s\n' "$label" "$url"
      return 0
    fi
    sleep 1
  done
  printf 'ERROR: %s did not become ready: %s\n' "$label" "$url" >&2
  return 1
}

wait_for_docker_health() {
  local container="$1"
  local label="$2"
  local attempts="${3:-40}"
  local i
  for i in $(seq 1 "$attempts"); do
    local status
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"
    if [[ "$status" == "healthy" || "$status" == "running" ]]; then
      printf '%s ready: %s (%s)\n' "$label" "$container" "$status"
      return 0
    fi
    sleep 1
  done
  printf 'ERROR: %s did not become ready: %s\n' "$label" "$container" >&2
  docker logs "$container" --tail 40 || true
  return 1
}

docker_container_exists() {
  local container="$1"
  docker ps -a --format '{{.Names}}' | grep -Fx "$container" >/dev/null 2>&1
}

docker_container_running() {
  local container="$1"
  docker ps --format '{{.Names}}' | grep -Fx "$container" >/dev/null 2>&1
}

ensure_postgres() {
  print_section "Postgres"
  if docker_container_exists "$POSTGRES_CONTAINER"; then
    if docker_container_running "$POSTGRES_CONTAINER"; then
      printf 'Reusing running container: %s\n' "$POSTGRES_CONTAINER"
    else
      printf 'Starting existing container: %s\n' "$POSTGRES_CONTAINER"
      docker start "$POSTGRES_CONTAINER" >/dev/null
    fi
  else
    printf 'Creating container: %s\n' "$POSTGRES_CONTAINER"
    docker volume create "$POSTGRES_VOLUME" >/dev/null
    docker run -d \
      --name "$POSTGRES_CONTAINER" \
      -e POSTGRES_DB="$POSTGRES_DB" \
      -e POSTGRES_USER="$POSTGRES_USER" \
      -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
      -v "${POSTGRES_VOLUME}:/var/lib/postgresql/data" \
      -p "127.0.0.1:${POSTGRES_PORT}:5432" \
      --health-cmd "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}" \
      --health-interval 5s \
      --health-timeout 3s \
      --health-retries 20 \
      "$POSTGRES_IMAGE" >/dev/null
  fi
  wait_for_docker_health "$POSTGRES_CONTAINER" "Postgres"
}

ensure_redis() {
  print_section "Redis"
  if docker_container_exists "$REDIS_CONTAINER"; then
    if docker_container_running "$REDIS_CONTAINER"; then
      printf 'Reusing running container: %s\n' "$REDIS_CONTAINER"
    else
      printf 'Starting existing container: %s\n' "$REDIS_CONTAINER"
      docker start "$REDIS_CONTAINER" >/dev/null
    fi
  else
    printf 'Creating container: %s\n' "$REDIS_CONTAINER"
    docker run -d \
      --name "$REDIS_CONTAINER" \
      -p "127.0.0.1:${REDIS_PORT}:6379" \
      --health-cmd "redis-cli ping" \
      --health-interval 5s \
      --health-timeout 3s \
      --health-retries 20 \
      "$REDIS_IMAGE" >/dev/null
  fi
  wait_for_docker_health "$REDIS_CONTAINER" "Redis"
}

start_process() {
  local label="$1"
  local pid_file="$2"
  local log_file="$3"
  shift 3

  clear_pid_file_if_stale "$pid_file"
  local existing_pid
  existing_pid="$(read_pid "$pid_file" || true)"
  if [[ -n "$existing_pid" ]] && is_pid_running "$existing_pid"; then
    printf '%s already running (pid=%s)\n' "$label" "$existing_pid"
    return 0
  fi

  printf 'Starting %s\n' "$label"
  (
    cd "$ROOT_DIR"
    nohup "$@" >>"$log_file" 2>&1 &
    echo $! >"$pid_file"
  )
}

start_backend() {
  print_section "Backend"
  local bridge_env=""
  if should_enable_symphony; then
    bridge_env="SYMPHONY_BRIDGE_BASE_URL=http://127.0.0.1:${SYMPHONY_PORT} SYMPHONY_BRIDGE_TOKEN=${SYMPHONY_BRIDGE_TOKEN} SYMPHONY_CALLBACK_TOKEN=${SYMPHONY_CALLBACK_TOKEN} SYMPHONY_STUB_AUTO_CALLBACK=false"
  fi
  start_process \
    "backend" \
    "$BACKEND_PID_FILE" \
    "$BACKEND_LOG_FILE" \
    "bash" \
    "-lc" \
    "cd '${ROOT_DIR}/backend' && ${bridge_env} ./.venv/bin/uvicorn app.main:app --port '${BACKEND_PORT}'"
  if ! wait_for_http "http://localhost:${BACKEND_PORT}/healthz" "Backend"; then
    print_log_tail "Backend" "$BACKEND_LOG_FILE"
    exit 1
  fi
}

start_worker() {
  print_section "Worker"
  local bridge_env=""
  if should_enable_symphony; then
    bridge_env="SYMPHONY_BRIDGE_BASE_URL=http://127.0.0.1:${SYMPHONY_PORT} SYMPHONY_BRIDGE_TOKEN=${SYMPHONY_BRIDGE_TOKEN} SYMPHONY_CALLBACK_TOKEN=${SYMPHONY_CALLBACK_TOKEN} SYMPHONY_STUB_AUTO_CALLBACK=false"
  fi
  start_process \
    "worker" \
    "$WORKER_PID_FILE" \
    "$WORKER_LOG_FILE" \
    "bash" \
    "-lc" \
    "cd '${ROOT_DIR}/backend' && ${bridge_env} ./.venv/bin/python -c \"from app.services.queue_worker import run_worker; run_worker()\""
}

start_frontend() {
  print_section "Frontend"
  start_process \
    "frontend" \
    "$FRONTEND_PID_FILE" \
    "$FRONTEND_LOG_FILE" \
    "bash" \
    "${ROOT_DIR}/scripts/with_node.sh" \
    "--cwd" \
    "${ROOT_DIR}/frontend" \
    "npm" \
    "run" \
    "dev"
  if ! wait_for_http "http://localhost:${FRONTEND_PORT}" "Frontend"; then
    print_log_tail "Frontend" "$FRONTEND_LOG_FILE"
    exit 1
  fi
}

should_enable_symphony() {
  case "$SYMPHONY_ENABLE" in
    1|true|TRUE|yes|YES) return 0 ;;
    0|false|FALSE|no|NO) return 1 ;;
    auto|AUTO|"")
      [[ -d "$SYMPHONY_DIR" && -f "$SYMPHONY_DIR/package.json" ]] || return 1
      [[ -d "$SYMPHONY_DIR/node_modules" ]] || return 1
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

render_symphony_workflow() {
  cat >"$SYMPHONY_WORKFLOW_FILE" <<EOF
---
tracker:
  kind: linear
  endpoint: http://127.0.0.1:9/graphql
  api_key: local-dev-token
  project_slug: local-dev
  active_states:
    - Todo
    - In Progress
  terminal_states:
    - Done
    - Closed
    - Cancelled
    - Canceled
    - Duplicate

polling:
  interval_ms: 600000

workspace:
  root: ${ROOT_DIR}/.tmp/local-dev/symphony/workspaces

hooks:
  timeout_ms: 1000

shared_memory:
  enabled: false

agent:
  max_concurrent_agents: 1
  max_turns: 1
  max_retry_backoff_ms: 300000

codex:
  command: codex
  fallback_command:
  turn_timeout_ms: 3600000
  read_timeout_ms: 10000
  stall_timeout_ms: 300000
---

You are a runtime worker executing a Mission Control-dispatched task.

## Task

**{{ issue.identifier }}**: {{ issue.title }}

{% if issue.description %}
{{ issue.description }}
{% endif %}

{% if issue.branch_name %}
Branch: {{ issue.branch_name }}
{% endif %}

{% if issue.url %}
Task URL: {{ issue.url }}
{% endif %}

Complete the task and report progress through the runtime callback channel.
EOF
}

start_symphony() {
  if ! should_enable_symphony; then
    print_section "Symphony"
    printf 'Skipping symphony bridge startup (SYMPHONY_ENABLE=%s)\n' "$SYMPHONY_ENABLE"
    if [[ ! -d "$SYMPHONY_DIR/node_modules" && -d "$SYMPHONY_DIR" ]]; then
      printf 'Hint: install dependencies in %s to enable local bridge mode.\n' "$SYMPHONY_DIR"
    fi
    return 0
  fi

  print_section "Symphony"
  render_symphony_workflow
  start_process \
    "symphony" \
    "$SYMPHONY_PID_FILE" \
    "$SYMPHONY_LOG_FILE" \
    "bash" \
    "${ROOT_DIR}/scripts/with_node.sh" \
    "--cwd" \
    "${SYMPHONY_DIR}" \
    "env" \
    "MISSION_CONTROL_BASE_URL=http://127.0.0.1:${BACKEND_PORT}" \
    "MISSION_CONTROL_BRIDGE_TOKEN=${SYMPHONY_BRIDGE_TOKEN}" \
    "MISSION_CONTROL_CALLBACK_TOKEN=${SYMPHONY_CALLBACK_TOKEN}" \
    "SYMPHONY_HTTP_BIND=127.0.0.1" \
    "SYMPHONY_HTTP_PORT=${SYMPHONY_PORT}" \
    "npm" \
    "run" \
    "dev" \
    "--" \
    "${SYMPHONY_WORKFLOW_FILE}" \
    "--port" \
    "${SYMPHONY_PORT}" \
    "--runner" \
    "codex"
  if ! wait_for_http "http://localhost:${SYMPHONY_PORT}/health" "Symphony bridge"; then
    print_log_tail "Symphony" "$SYMPHONY_LOG_FILE"
    exit 1
  fi
}

show_process_status() {
  local label="$1"
  local pid_file="$2"
  local pid
  pid="$(read_pid "$pid_file" || true)"
  if [[ -n "$pid" ]] && is_pid_running "$pid"; then
    printf '%s: running (pid=%s)\n' "$label" "$pid"
  else
    printf '%s: stopped\n' "$label"
  fi
}

stop_process() {
  local label="$1"
  local pid_file="$2"
  local pid
  pid="$(read_pid "$pid_file" || true)"
  if [[ -z "$pid" ]]; then
    printf '%s already stopped\n' "$label"
    return 0
  fi
  if is_pid_running "$pid"; then
    printf 'Stopping %s (pid=%s)\n' "$label" "$pid"
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    if is_pid_running "$pid"; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  fi
  rm -f "$pid_file"
}

status() {
  print_section "Containers"
  if docker_container_exists "$POSTGRES_CONTAINER"; then
    printf 'Postgres container: %s (%s)\n' \
      "$POSTGRES_CONTAINER" \
      "$(docker inspect -f '{{.State.Status}}' "$POSTGRES_CONTAINER" 2>/dev/null || true)"
  else
    printf 'Postgres container: missing\n'
  fi
  if docker_container_exists "$REDIS_CONTAINER"; then
    printf 'Redis container: %s (%s)\n' \
      "$REDIS_CONTAINER" \
      "$(docker inspect -f '{{.State.Status}}' "$REDIS_CONTAINER" 2>/dev/null || true)"
  else
    printf 'Redis container: missing\n'
  fi

  print_section "Processes"
  show_process_status "backend" "$BACKEND_PID_FILE"
  show_process_status "worker" "$WORKER_PID_FILE"
  show_process_status "frontend" "$FRONTEND_PID_FILE"
  show_process_status "symphony" "$SYMPHONY_PID_FILE"

  print_section "HTTP"
  if curl -fsS "http://localhost:${BACKEND_PORT}/healthz" >/dev/null 2>&1; then
    printf 'Backend: healthy\n'
  else
    printf 'Backend: unavailable\n'
  fi
  if curl -fsS "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1; then
    printf 'Frontend: reachable\n'
  else
    printf 'Frontend: unavailable\n'
  fi
  if should_enable_symphony && curl -fsS "http://localhost:${SYMPHONY_PORT}/health" >/dev/null 2>&1; then
    printf 'Symphony bridge: healthy\n'
  elif should_enable_symphony; then
    printf 'Symphony bridge: unavailable\n'
  fi

  print_section "Logs"
  printf 'Backend log: %s\n' "$BACKEND_LOG_FILE"
  printf 'Worker log: %s\n' "$WORKER_LOG_FILE"
  printf 'Frontend log: %s\n' "$FRONTEND_LOG_FILE"
  printf 'Symphony log: %s\n' "$SYMPHONY_LOG_FILE"
}

down() {
  print_section "Stopping local processes"
  stop_process "symphony" "$SYMPHONY_PID_FILE"
  stop_process "frontend" "$FRONTEND_PID_FILE"
  stop_process "worker" "$WORKER_PID_FILE"
  stop_process "backend" "$BACKEND_PID_FILE"

  print_section "Stopping containers"
  if docker_container_exists "$REDIS_CONTAINER"; then
    docker stop "$REDIS_CONTAINER" >/dev/null || true
    printf 'Stopped %s\n' "$REDIS_CONTAINER"
  fi
  if docker_container_exists "$POSTGRES_CONTAINER"; then
    docker stop "$POSTGRES_CONTAINER" >/dev/null || true
    printf 'Stopped %s\n' "$POSTGRES_CONTAINER"
  fi
}

reset() {
  down
  print_section "Removing containers and data"
  if docker_container_exists "$REDIS_CONTAINER"; then
    docker rm -f "$REDIS_CONTAINER" >/dev/null || true
    printf 'Removed %s\n' "$REDIS_CONTAINER"
  fi
  if docker_container_exists "$POSTGRES_CONTAINER"; then
    docker rm -f "$POSTGRES_CONTAINER" >/dev/null || true
    printf 'Removed %s\n' "$POSTGRES_CONTAINER"
  fi
  if docker volume inspect "$POSTGRES_VOLUME" >/dev/null 2>&1; then
    docker volume rm "$POSTGRES_VOLUME" >/dev/null || true
    printf 'Removed volume %s\n' "$POSTGRES_VOLUME"
  fi
  rm -rf "$RUNTIME_DIR"
}

up() {
  require_command docker
  require_command curl
  ensure_runtime_dirs
  ensure_postgres
  ensure_redis
  start_backend
  start_symphony
  start_worker
  start_frontend
  print_section "Ready"
  printf 'Local dev stack is up.\n'
  printf 'Backend:  http://localhost:%s\n' "$BACKEND_PORT"
  printf 'Frontend: http://localhost:%s\n' "$FRONTEND_PORT"
  if should_enable_symphony; then
    printf 'Symphony: http://localhost:%s\n' "$SYMPHONY_PORT"
  fi
  printf 'Next: bash scripts/local_e2e_preflight.sh\n'
}

ACTION="${1:-up}"

case "$ACTION" in
  up) up ;;
  status) status ;;
  down) down ;;
  reset) reset ;;
  *)
    usage
    exit 1
    ;;
esac
