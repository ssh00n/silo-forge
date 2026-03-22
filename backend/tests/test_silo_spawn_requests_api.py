# ruff: noqa: INP001
"""Integration tests for silo spawn request APIs."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin, require_org_member
from app.api.silos import router as silos_router
from app.api.silo_spawn_requests import router as silo_spawn_requests_router
from app.db.session import get_session
from app.models.boards import Board
from app.models.activity_events import ActivityEvent
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.models.tasks import Task
from app.models.users import User
from app.services.organizations import OrganizationContext


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


def _build_test_app(
    session_maker: async_sessionmaker[AsyncSession],
    ctx: OrganizationContext,
) -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(silo_spawn_requests_router)
    api_v1.include_router(silos_router)
    app.include_router(api_v1)

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_member() -> OrganizationContext:
        return ctx

    async def _override_require_org_admin() -> OrganizationContext:
        return ctx

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_member] = _override_require_org_member
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    return app


async def _seed_org_context(session: AsyncSession) -> tuple[OrganizationContext, Board, Task]:
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
        name="Demo Board",
        slug="demo-board",
    )
    task = Task(
        id=uuid4(),
        organization_id=organization.id,
        board_id=board.id,
        title="Investigate workload pressure",
        status="inbox",
        priority="high",
    )
    session.add(user)
    session.add(organization)
    session.add(membership)
    session.add(board)
    session.add(task)
    await session.commit()
    return OrganizationContext(organization=organization, member=membership), board, task


@pytest.mark.asyncio
async def test_create_and_list_silo_spawn_requests() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, _, _ = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            create_response = await client.post(
                "/api/v1/silos/spawn-requests",
                json={
                    "display_name": "Research pod",
                    "silo_kind": "agent",
                    "scope": "organization",
                    "summary": "Spin up a single-agent research silo.",
                },
            )
            list_response = await client.get("/api/v1/silos/spawn-requests")

        assert create_response.status_code == 201
        assert create_response.json()["slug"] == "research-pod"
        assert create_response.json()["status"] == "requested"
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1
        assert list_response.json()[0]["display_name"] == "Research pod"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_silo_spawn_request_records_activity() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, board, task = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/silos/spawn-requests",
                json={
                    "display_name": "Board worker",
                    "scope": "board",
                    "board_id": str(board.id),
                    "priority": "urgent",
                    "source_task_id": str(task.id),
                },
            )
        assert response.status_code == 201
        async with session_maker() as session:
            events = list(await session.exec(select(ActivityEvent).order_by(ActivityEvent.created_at)))
        assert events[-1].event_type == "silo.request.created"
        assert events[-1].board_id == board.id
        assert events[-1].payload["priority"] == "urgent"
        assert events[-1].payload["source_task_title"] == "Investigate workload pressure"
        assert events[-1].payload["source_task_status"] == "inbox"
        assert events[-1].payload["source_task_priority"] == "high"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_materialize_silo_spawn_request_when_silo_is_created() -> None:
    from app.models.gateways import Gateway

    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, _, _ = await _seed_org_context(session)
        gateway = Gateway(
            id=uuid4(),
            organization_id=ctx.organization.id,
            name="Fox Host",
            url="http://gateway.local",
            workspace_root="/srv/openclaw",
        )
        session.add(gateway)
        await session.commit()
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            request_response = await client.post(
                "/api/v1/silos/spawn-requests",
                json={"display_name": "Research pod", "scope": "organization"},
            )
            assert request_response.status_code == 201
            request_id = request_response.json()["id"]

            create_response = await client.post(
                "/api/v1/silos",
                json={
                    "name": "Research pod",
                    "blueprint_slug": "default-four-agent",
                    "spawn_request_id": request_id,
                },
            )
            refreshed_request = await client.get(f"/api/v1/silos/spawn-requests/{request_id}")

        assert create_response.status_code == 201
        assert refreshed_request.status_code == 200
        assert refreshed_request.json()["status"] == "materialized"
        assert refreshed_request.json()["materialized_silo_id"] is not None
        assert refreshed_request.json()["materialized_silo_slug"] == "research-pod"
        assert refreshed_request.json()["materialized_at"] is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_board_scoped_silo_spawn_request_requires_board() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, _, _ = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/silos/spawn-requests",
                json={
                    "display_name": "Board worker",
                    "scope": "board",
                },
            )

        assert response.status_code == 422
        assert "board_id is required" in response.text
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_board_scoped_silo_spawn_request_validates_board_membership() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, _, _ = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/silos/spawn-requests",
                json={
                    "display_name": "Board worker",
                    "scope": "board",
                    "board_id": str(uuid4()),
                },
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Board not found"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_board_scoped_silo_spawn_request_links_source_task() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, board, task = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/silos/spawn-requests",
                json={
                    "display_name": "Task support silo",
                    "scope": "board",
                    "board_id": str(board.id),
                    "source_task_id": str(task.id),
                },
            )

        assert response.status_code == 201
        assert response.json()["source_task_id"] == str(task.id)
        assert response.json()["source_task_title"] == task.title
        assert response.json()["source_task_status"] == task.status
        assert response.json()["source_task_priority"] == task.priority
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_board_scoped_silo_spawn_request_rejects_task_from_other_board() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, board, _ = await _seed_org_context(session)
        other_board = Board(
            id=uuid4(),
            organization_id=ctx.organization.id,
            name="Other Board",
            slug="other-board",
        )
        other_task = Task(
            id=uuid4(),
            organization_id=ctx.organization.id,
            board_id=other_board.id,
            title="Unrelated task",
            status="inbox",
            priority="medium",
        )
        session.add(other_board)
        session.add(other_task)
        await session.commit()
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/silos/spawn-requests",
                json={
                    "display_name": "Broken task silo",
                    "scope": "board",
                    "board_id": str(board.id),
                    "source_task_id": str(other_task.id),
                },
            )

        assert response.status_code == 422
        assert response.json()["detail"] == "source_task_id must belong to the selected board"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_silo_spawn_request_status() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, _, _ = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            create_response = await client.post(
                "/api/v1/silos/spawn-requests",
                json={"display_name": "Board worker", "scope": "organization"},
            )
            request_id = create_response.json()["id"]
            patch_response = await client.patch(
                f"/api/v1/silos/spawn-requests/{request_id}",
                json={"status": "planned", "priority": "high"},
            )

        assert patch_response.status_code == 200
        assert patch_response.json()["status"] == "planned"
        assert patch_response.json()["priority"] == "high"
    finally:
        await engine.dispose()
