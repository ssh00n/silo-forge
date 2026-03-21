# ruff: noqa: INP001
"""Tests for task execution dispatch scaffolding."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.task_execution_callbacks import router as task_execution_callbacks_router
from app.api.task_execution_runs import router as task_execution_runs_router
from app.core.config import settings
from app.db.session import get_session
from app.models.activity_events import ActivityEvent
from app.models.agents import Agent
from app.models.boards import Board
from app.models.organizations import Organization
from app.models.organization_members import OrganizationMember
from app.models.silo_roles import SiloRole
from app.models.silos import Silo
from app.models.tasks import Task
from app.models.users import User
from app.services.organizations import OrganizationContext
from app.services.task_execution_runs import TaskExecutionRunService
from app.schemas.task_execution_runs import TaskExecutionRunCreate


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
    api_v1.include_router(task_execution_callbacks_router)
    app.include_router(api_v1)

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return ctx

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    return app


async def _seed_context(session: AsyncSession) -> tuple[OrganizationContext, Board, Task, Silo, Agent]:
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
        title="Dispatch through Symphony contract",
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
        workspace_root="/srv/symphony",
    )
    lead = Agent(
        id=uuid4(),
        board_id=board.id,
        gateway_id=uuid4(),
        name="Lead Agent",
        status="online",
        is_board_lead=True,
    )
    session.add(user)
    session.add(organization)
    session.add(membership)
    session.add(board)
    session.add(task)
    session.add(silo)
    session.add(symphony_role)
    session.add(lead)
    await session.commit()
    return OrganizationContext(organization=organization, member=membership), board, task, silo, lead


@pytest.mark.asyncio
async def test_dispatch_run_marks_run_as_dispatching_with_stub_contract() -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        _, board, task, silo, _lead = await _seed_context(session)
        service = TaskExecutionRunService(session)
        created = await service.create_run(
            board=board,
            task=task,
            payload=TaskExecutionRunCreate(silo_slug=silo.slug),
        )
        dispatched = await service.dispatch_run(
            organization_id=board.organization_id,
            board_id=board.id,
            task_id=task.id,
            run_id=created.id,
        )

    try:
        assert dispatched.status == "dispatching"
        assert dispatched.external_run_id == f"mc-{created.id}"
        assert dispatched.workspace_path == "/srv/symphony/mission-control/MC-" + str(task.id)[:8]
        assert dispatched.result_payload is not None
        assert dispatched.result_payload["dispatch_acceptance"]["adapter_mode"] == "stub"
        async with session_maker() as session:
            event = (
                await session.exec(
                    select(ActivityEvent)
                    .where(col(ActivityEvent.task_id) == task.id)
                    .where(col(ActivityEvent.event_type) == "task.execution_run.dispatched")
                    .order_by(col(ActivityEvent.created_at).desc())
                )
            ).first()
            assert event is not None
            assert event.message is not None
            assert "Dispatched Symphony run" in event.message
            assert "via stub adapter" in event.message
            assert "Workspace:" in event.message
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_dispatch_endpoint_enqueues_background_task(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, board, task, silo, _lead = await _seed_context(session)
        service = TaskExecutionRunService(session)
        created = await service.create_run(
            board=board,
            task=task,
            payload=TaskExecutionRunCreate(silo_slug=silo.slug),
        )
    app = _build_test_app(session_maker, ctx)

    monkeypatch.setattr(
        "app.api.task_execution_runs.enqueue_task_execution_dispatch",
        lambda payload: True,
    )

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post(
                f"/api/v1/boards/{board.id}/tasks/{task.id}/execution-runs/{created.id}/dispatch"
            )

        assert response.status_code == 200
        assert response.json()["status"] == "queued"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_dispatch_run_posts_to_configured_http_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, session_maker = await _make_engine()
    original_base_url = settings.symphony_bridge_base_url
    original_token = settings.symphony_bridge_token
    async with session_maker() as session:
        _, board, task, silo, _lead = await _seed_context(session)
        service = TaskExecutionRunService(session)
        created = await service.create_run(
            board=board,
            task=task,
            payload=TaskExecutionRunCreate(silo_slug=silo.slug),
        )

        async def handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url) == "http://symphony.local/api/v1/mission-control/dispatches"
            assert request.headers.get("Authorization") == "Bearer bridge-token"
            body = await request.aread()
            assert b'"callback_url"' in body
            return httpx.Response(
                200,
                json={
                    "accepted": True,
                    "external_run_id": "sym-run-1",
                    "workspace_path": "/remote/workspaces/MC-123",
                    "branch_name": "feature/http-bridge",
                    "summary": "Accepted by Symphony bridge.",
                },
            )

        original_async_client = httpx.AsyncClient
        monkeypatch.setattr(
            "app.services.task_execution_dispatch.httpx.AsyncClient",
            lambda **kwargs: original_async_client(transport=httpx.MockTransport(handler)),
        )
        settings.symphony_bridge_base_url = "http://symphony.local"
        settings.symphony_bridge_token = "bridge-token"
        try:
            dispatched = await service.dispatch_run(
                organization_id=board.organization_id,
                board_id=board.id,
                task_id=task.id,
                run_id=created.id,
            )
        finally:
            settings.symphony_bridge_base_url = original_base_url
            settings.symphony_bridge_token = original_token

    try:
        assert dispatched.status == "dispatching"
        assert dispatched.external_run_id == "sym-run-1"
        assert dispatched.workspace_path == "/remote/workspaces/MC-123"
        assert dispatched.branch_name == "feature/http-bridge"
        assert dispatched.result_payload is not None
        assert dispatched.result_payload["dispatch_acceptance"]["adapter_mode"] == "http"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_symphony_callback_updates_execution_run_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, session_maker = await _make_engine()
    original_callback_token = settings.symphony_callback_token
    settings.symphony_callback_token = "callback-token"
    async with session_maker() as session:
        ctx, board, task, silo, _lead = await _seed_context(session)
        service = TaskExecutionRunService(session)
        created = await service.create_run(
            board=board,
            task=task,
            payload=TaskExecutionRunCreate(silo_slug=silo.slug),
        )
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post(
                f"/api/v1/task-execution-runs/{created.id}/callbacks/symphony",
                headers={"X-Symphony-Token": "callback-token"},
                json={
                    "status": "running",
                    "external_run_id": "sym-live-1",
                    "workspace_path": "/srv/symphony/mission-control/MC-live",
                    "branch_name": "feature/live",
                    "summary": "Worker picked up the run.",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "running"
        assert body["external_run_id"] == "sym-live-1"
        assert body["workspace_path"] == "/srv/symphony/mission-control/MC-live"
        async with session_maker() as session:
            refreshed_task = await session.get(Task, task.id)
            assert refreshed_task is not None
            assert refreshed_task.status == "in_progress"
            updated_event = (
                await session.exec(
                    select(ActivityEvent)
                    .where(col(ActivityEvent.task_id) == task.id)
                    .where(col(ActivityEvent.event_type) == "task.execution_run.updated")
                    .order_by(col(ActivityEvent.created_at).desc())
                )
            ).first()
            assert updated_event is not None
            assert updated_event.message is not None
            assert "is running" in updated_event.message
            assert "feature/live" in updated_event.message
    finally:
        settings.symphony_callback_token = original_callback_token
        await engine.dispose()


@pytest.mark.asyncio
async def test_symphony_callback_succeeded_moves_task_to_review_and_records_comment() -> None:
    engine, session_maker = await _make_engine()
    original_callback_token = settings.symphony_callback_token
    settings.symphony_callback_token = "callback-token"
    async with session_maker() as session:
        ctx, board, task, silo, lead = await _seed_context(session)
        task.status = "in_progress"
        session.add(task)
        await session.commit()
        service = TaskExecutionRunService(session)
        created = await service.create_run(
            board=board,
            task=task,
            payload=TaskExecutionRunCreate(silo_slug=silo.slug),
        )
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post(
                f"/api/v1/task-execution-runs/{created.id}/callbacks/symphony",
                headers={"X-Symphony-Token": "callback-token"},
                json={
                    "status": "succeeded",
                    "external_run_id": "sym-live-2",
                    "workspace_path": "/srv/symphony/mission-control/MC-live-2",
                    "branch_name": "feature/live-2",
                    "pr_url": "https://github.com/example/repo/pull/22",
                    "summary": "Opened PR with implementation updates.",
                },
            )

        assert response.status_code == 200
        async with session_maker() as session:
            refreshed_task = await session.get(Task, task.id)
            assert refreshed_task is not None
            assert refreshed_task.status == "review"
            assert refreshed_task.assigned_agent_id == lead.id
            comments = list(
                await session.exec(
                    select(ActivityEvent)
                    .where(col(ActivityEvent.task_id) == task.id)
                    .where(col(ActivityEvent.event_type) == "task.execution_run.report")
                    .order_by(col(ActivityEvent.created_at).desc())
                )
            )
            assert comments
            assert comments[0].message is not None
            assert "Opened PR with implementation updates." in comments[0].message
            assert "https://github.com/example/repo/pull/22" in comments[0].message
    finally:
        settings.symphony_callback_token = original_callback_token
        await engine.dispose()


@pytest.mark.asyncio
async def test_symphony_callback_succeeded_respects_review_comment_gate() -> None:
    engine, session_maker = await _make_engine()
    original_callback_token = settings.symphony_callback_token
    settings.symphony_callback_token = "callback-token"
    async with session_maker() as session:
        ctx, board, task, silo, _lead = await _seed_context(session)
        board.comment_required_for_review = True
        task.status = "in_progress"
        session.add(board)
        session.add(task)
        await session.commit()
        service = TaskExecutionRunService(session)
        created = await service.create_run(
            board=board,
            task=task,
            payload=TaskExecutionRunCreate(silo_slug=silo.slug),
        )
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post(
                f"/api/v1/task-execution-runs/{created.id}/callbacks/symphony",
                headers={"X-Symphony-Token": "callback-token"},
                json={
                    "status": "succeeded",
                    "summary": "Ready for review but board requires a worker comment gate.",
                },
            )

        assert response.status_code == 200
        async with session_maker() as session:
            refreshed_task = await session.get(Task, task.id)
            assert refreshed_task is not None
            assert refreshed_task.status == "in_progress"
            comments = list(
                await session.exec(
                    select(ActivityEvent)
                    .where(col(ActivityEvent.task_id) == task.id)
                    .where(col(ActivityEvent.event_type) == "task.execution_run.report")
                )
            )
            assert comments
    finally:
        settings.symphony_callback_token = original_callback_token
        await engine.dispose()
