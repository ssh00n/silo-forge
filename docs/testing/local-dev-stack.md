# Local Dev Stack

Use this when you want one command to manage the full local E2E stack.

It covers:

- local Postgres in Docker
- local Redis in Docker
- backend API
- queue worker
- frontend dev server

## Commands

From repo root:

```bash
bash scripts/local_dev_stack.sh up
```

Check status:

```bash
bash scripts/local_dev_stack.sh status
```

Stop services:

```bash
bash scripts/local_dev_stack.sh down
```

Stop services and wipe local Docker data:

```bash
bash scripts/local_dev_stack.sh reset
```

## Behavior

`up` will:

- reuse existing Postgres and Redis containers if they already exist
- create them if they do not exist
- wait for both to become healthy
- start backend, worker, and frontend as background processes
- store PID files and logs under `.tmp/local-dev/`

## Runtime files

- backend log: `.tmp/local-dev/logs/backend.log`
- worker log: `.tmp/local-dev/logs/worker.log`
- frontend log: `.tmp/local-dev/logs/frontend.log`

## Default local resources

- Postgres container: `mc-local-postgres`
- Postgres volume: `mc_local_postgres_data`
- Redis container: `mc-local-redis`

## Notes

- `reset` removes the local Postgres volume, so it clears seeded data too.
- The script does not overwrite your env files. It assumes `backend/.env` and `frontend/.env` are already valid for local development.
- After `up`, continue with:

```bash
bash scripts/local_e2e_preflight.sh
```
