# Local E2E Preflight

Run this before browser-based local E2E.

It is the final readiness gate for:

- local auth mode
- backend/frontend reachability
- minimal demo seed path
- silo/runtime activity scenarios

## Fast path

From repo root:

```bash
bash scripts/local_e2e_preflight.sh
```

The script checks:

- `.env`, `backend/.env`, `frontend/.env` exist
- backend `AUTH_MODE=local`
- frontend `NEXT_PUBLIC_AUTH_MODE=local`
- `LOCAL_AUTH_TOKEN` exists and is at least 50 chars
- frontend API base is configured
- backend health responds on `http://localhost:8000/healthz`
- frontend responds on `http://localhost:3000`

## Expected local dev process layout

Terminal 1:

```bash
docker compose -f compose.yml --env-file .env up -d db
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
npm run dev
```

## Minimal demo seed

If you do not already have a usable board/gateway/user dataset:

```bash
cd backend
uv run python scripts/seed_demo.py
```

What it gives you:

- one demo gateway
- one demo board
- one demo admin user row
- one online lead agent
- one demo task assigned to the lead
- one `demo-silo` based on `default-four-agent`
- gateway assignments for `fox`, `bunny`, `owl`, and `otter`
- Symphony and telemetry enabled on that silo

Note:

- this is enough to begin the local silo/runtime E2E runbook directly
- you can still create extra silos manually if you want broader coverage

## Manual readiness checklist

Confirm these before browser E2E:

1. You can sign in with local auth in the frontend.
2. Dashboard loads without auth or API errors.
3. A board exists and opens normally.
4. A gateway exists and is visible in settings.
5. A silo exists with at least one assigned gateway-backed role.
6. `Validate runtime` works on that silo.
7. Board live feed opens and shows baseline activity.
8. Dashboard recent activity updates after a new event.

## Next document

After preflight passes, move to:

- [Local E2E: Silo Runtime And Activity](./local-e2e-silo-runtime.md)
