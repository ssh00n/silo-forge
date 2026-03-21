# Local E2E: Silo Runtime And Activity

This runbook is the last step before browser-driven local E2E validation.

It focuses on the current Silo Forge control-plane flow:

- create or update a silo
- validate/apply runtime bundles
- trigger task-backed Symphony execution runs
- confirm activity propagation in dashboard, activity feed, and board live feed

## Prerequisites

From repo root:

```bash
make setup
docker compose -f compose.yml --env-file .env up -d db
```

Run backend and frontend in separate terminals:

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm run dev
```

Recommended env:

- `AUTH_MODE=local`
- `LOCAL_AUTH_TOKEN=<same token in backend/frontend local auth config>`
- `NEXT_PUBLIC_API_URL=auto`

## Seed State

Confirm you have:

- one organization owner/admin user
- at least one gateway
- at least one board connected to that gateway
- one silo with at least one assigned gateway role

If you ran `scripts/seed_demo.py`, this state should already exist as:

- `Demo Organization`
- `demo@example.com`
- `Demo Gateway`
- `Demo Board`
- `Demo Silo` (`demo-silo`)
- one sample task titled `Ship silo runtime E2E flow`

Minimum useful manual setup, if you did not use the seed script:

1. Create a board.
2. Create a silo from `default-four-agent`.
3. Assign the `fox` role to the same gateway as the board.
4. Open the silo detail and run `Validate runtime`.

## Scenario 1: Runtime Activity Propagation

Goal: verify `silo.runtime.*` and gateway-linked activity propagate everywhere.

1. Open dashboard.
2. Set `Recent Activity` filter to `Runtime`.
3. In another tab, run silo runtime `validate`.
4. Confirm a new `silo.runtime.validate` event appears without waiting for query refresh.
5. Open `/activity?category=runs` and confirm runtime execution events still render correctly.
6. Open a board that uses the same gateway and open `Live feed`.
7. Set live feed filter to `Gateway`.
8. Confirm related `silo.runtime.*`, `gateway.*`, or `agent lifecycle` events appear when relevant.

Expected result:

- dashboard recent activity updates in near realtime
- board live feed shows gateway/runtime events tied to the board gateway or board tasks
- event details render structured payload fields, not only raw strings

## Scenario 2: Task Execution Run Loop

Goal: verify the control-plane loop closes on one task.

1. Open a board task.
2. Use `Run with Symphony`.
3. Confirm a new execution run appears in the task panel.
4. Confirm dashboard `Runtime Runs` updates.
5. Confirm board live feed `Runs` filter shows queued/dispatched/report events.
6. Confirm global `/activity?category=runs` shows the same run lifecycle.
7. If the run fails, use `Retry`.

When a real local Symphony bridge is available through `scripts/local_dev_stack.sh`,
task execution runs should flow through the HTTP bridge and callback endpoint.

When no real Symphony bridge is configured in local `dev`, the worker can still
close the loop with synthetic stub callbacks. That means local E2E should still
move from `dispatching` into `running` and `succeeded`.

Expected result:

- task panel, board live feed, dashboard, and activity page all agree on the run status
- structured fields such as `PR`, `Branch`, `Tokens`, `Workspace`, `External run` render consistently

## Scenario 3: Board Gateway Activity

Goal: verify board-scoped gateway coordination is visible.

1. Trigger an action that emits one of:
   - `gateway.main.lead_message.sent`
   - `gateway.lead.ask_user.sent`
   - `agent.nudge.sent`
   - `agent.<action>.direct`
2. Keep the board live feed open with `Gateway` or `Agents` selected.
3. Confirm the event appears without needing a manual refresh.

Expected result:

- payload-derived detail rows show gateway name, agent name, action, delivery status, and error when present

## Failure Checks

If realtime updates do not appear:

1. Confirm backend logs show `/api/v1/activity/stream` requests.
2. Confirm browser network tab shows a live `text/event-stream` response.
3. Confirm the event has a matching `board_id`, `task_id`, or `gateway_id` payload for board live feed relevance.
4. Confirm the event type is included in current frontend filter mappings.

## Exit Criteria

Ready for browser E2E only when all are true:

- dashboard recent activity updates without full-page refresh
- board live feed receives runtime/gateway activity in realtime
- runtime run loop works from task detail through report or retry
- payload-based event details render correctly across dashboard, board, and activity feed
