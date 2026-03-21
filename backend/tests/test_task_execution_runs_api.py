# ruff: noqa: INP001
"""Integration tests for task-backed execution run APIs."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.task_execution_runs import router as task_execution_runs_router
from app.db.session import get_session
from app.models.activity_events import ActivityEvent
from app.models.boards import Board
from app.models.organizations import Organization
from app.models.organization_members import OrganizationMember
from app.models.silo_roles import SiloRole
from app.models.silos import Silo
from app.models.tasks import Task
from app.models.users import User
from app.services.organizations import OrganizationContext


async def _make_engine() -> tuple[object, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _build_test_app(
    session_maker: async_sessionmaker[AsyncSession],
    ctx: OrganizationContext,
) -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(task_execution_runs_router)
    app.include_router(api_v1)

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return ctx

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    return app


async def _seed_context(session: AsyncSession) -> tuple[OrganizationContext, Board, Task, Silo]:
    user = User(
        id=uuid4(),
        clerk_user_id=f"clerk_{uuid4().hex}",
        email="admin@example.com",
        name="Admin",
    )
    organization = Organization(id=uuid4(), name="Personal")
    membership = OrganizationMember(
        id=uuid4(),
        organization_id=organization.id,
        user_id=user.id,
        role="owner",
        all_boards_read=True,
        all_boards_write=True,
    )
    board = Board(
        id=uuid4(),
        organization_id=organization.id,
        name="Delivery",
        slug="delivery",
    )
    task = Task(
        id=uuid4(),
        organization_id=organization.id,
        board_id=board.id,
        title="Implement task-backed Symphony dispatch",
        status="inbox",
    )
    silo = Silo(
        id=uuid4(),
        organization_id=organization.id,
        slug="demo-silo",
        name="Demo Silo",
        blueprint_slug="default-four-agent",
        blueprint_version="0.1.0",
        enable_symphony=True,
    )
    symphony_role = SiloRole(
        id=uuid4(),
        silo_id=silo.id,
        slug="symphony",
        display_name="Symphony",
        role_type="orchestrator",
        runtime_kind="symphony",
        host_kind="ec2",
    )
    session.add(user)
    session.add(organization)
    session.add(membership)
    session.add(board)
    session.add(task)
    session.add(silo)
    session.add(symphony_role)
    await session.commit()
    return OrganizationContext(organization=organization, member=membership), board, task, silo


@pytest.mark.asyncio
async def test_create_task_execution_run_queues_symphony_run() -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, board, task, silo = await _seed_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs",
                json={"silo_slug": silo.slug},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "queued"
        assert body["executor_kind"] == "symphony"
        assert body["role_slug"] == "symphony"
        assert body["task_snapshot"]["title"] == task.title
        async with session_maker() as session:
            event = (
                await session.exec(
                    select(ActivityEvent)
                    .where(col(ActivityEvent.task_id) == task.id)
                    .where(col(ActivityEvent.event_type) == "task.execution_run.created")
                    .order_by(col(ActivityEvent.created_at).desc())
                )
            ).first()
            assert event is not None
            assert event.message is not None
            assert "Queued Symphony run" in event.message
            assert f"{silo.slug}/symphony" in event.message
            assert event.payload is not None
            assert event.payload["run_id"] == body["id"]
            assert event.payload["status"] == "queued"
            assert event.payload["silo_slug"] == silo.slug
            assert event.payload["role_slug"] == "symphony"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_list_task_execution_runs_returns_newest_first() -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, board, task, silo = await _seed_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            first = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs",
                json={"silo_slug": silo.slug},
            )
            second = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs",
                json={
                    "silo_slug": silo.slug,
                    "branch_name_hint": "feature/task-backed-symphony",
                },
            )
            response = await client.get(f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs")

        assert first.status_code == 201
        assert second.status_code == 201
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["dispatch_payload"]["branch_name_hint"] == "feature/task-backed-symphony"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_dispatch_task_execution_run_creates_and_enqueues(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, board, task, silo = await _seed_context(session)
    app = _build_test_app(session_maker, ctx)
    enqueued: list[object] = []
    monkeypatch.setattr(
        "app.api.task_execution_runs.enqueue_task_execution_dispatch",
        lambda payload: enqueued.append(payload) or True,
    )

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs/dispatch",
                json={
                    "silo_slug": silo.slug,
                    "branch_name_hint": "feature/direct-dispatch",
                },
            )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "queued"
        assert body["dispatch_payload"]["branch_name_hint"] == "feature/direct-dispatch"
        assert enqueued
        payload = enqueued[0]
        assert str(payload.run_id) == body["id"]
        assert str(payload.board_id) == str(board.id)
        assert str(payload.task_id) == str(task.id)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_task_execution_run_persists_result_fields() -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, board, task, silo = await _seed_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            create_response = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs",
                json={"silo_slug": silo.slug},
            )
            run_id = create_response.json()["id"]
            update_response = await client.patch(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs/{run_id}",
                json={
                    "status": "succeeded",
                    "external_run_id": "sym-123",
                    "workspace_path": "/srv/symphony/MT-101",
                    "branch_name": "feature/task-backed-symphony",
                    "pr_url": "https://github.com/example/repo/pull/1",
                    "summary": "Opened PR with initial implementation scaffold.",
                    "result_payload": {"pull_request": 1},
                },
            )

        assert update_response.status_code == 200
        body = update_response.json()
        assert body["status"] == "succeeded"
        assert body["external_run_id"] == "sym-123"
        assert body["pr_url"] == "https://github.com/example/repo/pull/1"
        assert body["result_payload"]["pull_request"] == 1
        assert body["completed_at"] is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_task_execution_run_rejects_silos_without_symphony() -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, board, task, silo = await _seed_context(session)
        silo.enable_symphony = False
        session.add(silo)
        await session.commit()
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs",
                json={"silo_slug": silo.slug},
            )

        assert response.status_code == 422
        assert "does not have Symphony enabled" in response.json()["detail"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_retry_task_execution_run_clones_failed_run_into_new_queue_entry() -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, board, task, silo = await _seed_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            create_response = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs",
                json={
                    "silo_slug": silo.slug,
                    "role_slug": "symphony",
                    "prompt_override": "retry me",
                    "branch_name_hint": "feature/retry-me",
                    "input_metadata": {"origin": "dashboard"},
                },
            )
            run_id = create_response.json()["id"]
            failed_response = await client.patch(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs/{run_id}",
                json={"status": "failed", "summary": "Run failed."},
            )
            retry_response = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs/{run_id}/retry"
            )
            list_response = await client.get(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs"
            )

        assert failed_response.status_code == 200
        assert retry_response.status_code == 201
        retried = retry_response.json()
        assert retried["id"] != run_id
        assert retried["status"] == "queued"
        assert retried["dispatch_payload"]["branch_name_hint"] == "feature/retry-me"
        assert retried["dispatch_payload"]["prompt_override"] == "retry me"
        assert retried["dispatch_payload"]["input_metadata"] == {"origin": "dashboard"}
        assert list_response.status_code == 200
        assert len(list_response.json()) == 2
        async with session_maker() as session:
            event = (
                await session.exec(
                    select(ActivityEvent)
                    .where(col(ActivityEvent.task_id) == task.id)
                    .where(col(ActivityEvent.event_type) == "task.execution_run.retried")
                    .order_by(col(ActivityEvent.created_at).desc())
                )
            ).first()
            assert event is not None
            assert event.message is not None
            assert "Retried Symphony run" in event.message
            assert "feature/retry-me" in event.message
            assert event.payload is not None
            assert event.payload["retried_from_run_id"] == run_id
            assert event.payload["status"] == "queued"
            assert event.payload["branch_hint"] == "feature/retry-me"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_retry_dispatch_task_execution_run_enqueues_replacement(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, board, task, silo = await _seed_context(session)
    app = _build_test_app(session_maker, ctx)
    enqueued: list[object] = []
    monkeypatch.setattr(
        "app.api.task_execution_runs.enqueue_task_execution_dispatch",
        lambda payload: enqueued.append(payload) or True,
    )

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            create_response = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs",
                json={"silo_slug": silo.slug},
            )
            run_id = create_response.json()["id"]
            await client.patch(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs/{run_id}",
                json={"status": "failed", "summary": "Run failed."},
            )
            retry_response = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs/{run_id}/retry-dispatch"
            )

        assert retry_response.status_code == 201
        body = retry_response.json()
        assert body["status"] == "queued"
        assert enqueued
        payload = enqueued[0]
        assert str(payload.run_id) == body["id"]
        assert str(payload.board_id) == str(board.id)
        assert str(payload.task_id) == str(task.id)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_dispatch_task_execution_run_falls_back_to_immediate_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, board, task, silo = await _seed_context(session)
    app = _build_test_app(session_maker, ctx)

    monkeypatch.setattr(
        "app.api.task_execution_runs.enqueue_task_execution_dispatch",
        lambda payload: False,
    )

    async def _dispatch_run(self, *, organization_id, board_id, task_id, run_id, adapter=None):
        run = await self.get_run(
            organization_id=organization_id,
            board_id=board_id,
            task_id=task_id,
            run_id=run_id,
        )
        assert run is not None
        return TaskExecutionRunRead.model_validate(
            {
                **run.model_dump(mode="json"),
                "status": "dispatching",
                "summary": "Dispatched immediately without Redis queue.",
            },
        )

    monkeypatch.setattr(
        TaskExecutionRunService,
        "dispatch_run",
        _dispatch_run,
    )

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs/dispatch",
                json={"silo_slug": silo.slug},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "dispatching"
        assert body["summary"] == "Dispatched immediately without Redis queue."
    finally:
        await engine.dispose()
