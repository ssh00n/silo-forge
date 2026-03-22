# ruff: noqa: INP001
"""Integration tests for persisted silo runtime orchestration APIs."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.silo_runtime import router as silo_runtime_router
from app.api.silos import router as silos_router
from app.db.session import get_session
from app.models.activity_events import ActivityEvent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
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
    api_v1.include_router(silos_router)
    api_v1.include_router(silo_runtime_router)
    app.include_router(api_v1)

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return ctx

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    return app


async def _seed_org_context(session: AsyncSession) -> tuple[OrganizationContext, Gateway]:
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
    gateway = Gateway(
        id=uuid4(),
        organization_id=organization.id,
        name="Fox Host",
        url="http://gateway.local",
        token="gateway-token",
        workspace_root="/srv/openclaw",
    )
    session.add(user)
    session.add(organization)
    session.add(membership)
    session.add(gateway)
    await session.commit()
    return OrganizationContext(organization=organization, member=membership), gateway


@pytest.mark.asyncio
async def test_validate_silo_runtime_calls_picoclaw_validate_for_assigned_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, gateway = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://gateway.local/api/system/runtime-bundles/validate"
        assert request.headers.get("Authorization") == "Bearer gateway-token"
        return httpx.Response(
            200,
            json={
                "valid": True,
                "restart_required": True,
                "warnings": [],
                "writes": [],
                "resolved_secrets": [],
            },
        )

    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.silos.runtime_apply.httpx.AsyncClient",
        lambda **kwargs: original_async_client(transport=httpx.MockTransport(handler)),
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            create_response = await client.post(
                "/api/v1/silos",
                json={
                    "name": "Demo Silo",
                    "blueprint_slug": "default-four-agent",
                    "gateway_assignments": [{"role_slug": "fox", "gateway_id": str(gateway.id)}],
                },
            )
            assert create_response.status_code == 201

            response = await client.post("/api/v1/silos/demo-silo/runtime/validate")

        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "validate"
        fox = next(item for item in body["results"] if item["role_slug"] == "fox")
        assert fox["validated"]["valid"] is True
        bunny = next(item for item in body["results"] if item["role_slug"] == "bunny")
        assert bunny["supports_picoclaw_bundle_apply"] is False
        assert "No gateway assignment" in bunny["warnings"][0]
        async with session_maker() as session:
            activity = (
                await session.exec(
                    select(ActivityEvent).where(
                        ActivityEvent.event_type == "silo.runtime.validate"
                    ),
                )
            ).one()
        assert activity.payload is not None
        assert activity.payload["silo_slug"] == "demo-silo"
        assert activity.payload["mode"] == "validate"
        assert activity.payload["result_count"] == "4"
        assert activity.payload["restart_required"] == "yes"
        assert activity.payload["gateway_ids"] == str(gateway.id)
        assert activity.board_id is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_apply_silo_runtime_calls_picoclaw_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, gateway = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://gateway.local/api/system/runtime-bundles/apply"
        return httpx.Response(
            200,
            json={
                "applied": True,
                "restart_required": True,
                "warnings": [],
                "writes": [],
                "resolved_secrets": [],
            },
        )

    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.silos.runtime_apply.httpx.AsyncClient",
        lambda **kwargs: original_async_client(transport=httpx.MockTransport(handler)),
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            create_response = await client.post(
                "/api/v1/silos",
                json={
                    "name": "Demo Silo",
                    "blueprint_slug": "default-four-agent",
                    "gateway_assignments": [{"role_slug": "fox", "gateway_id": str(gateway.id)}],
                },
            )
            assert create_response.status_code == 201

            response = await client.post("/api/v1/silos/demo-silo/runtime/apply")

        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "apply"
        fox = next(item for item in body["results"] if item["role_slug"] == "fox")
        assert fox["applied"]["applied"] is True
        async with session_maker() as session:
            activity = (
                await session.exec(
                    select(ActivityEvent).where(ActivityEvent.event_type == "silo.runtime.apply"),
                )
            ).one()
        assert activity.payload is not None
        assert activity.payload["silo_name"] == "Demo Silo"
        assert activity.payload["mode"] == "apply"
        assert activity.payload["roles"] == "fox, bunny, owl, otter"
        assert activity.payload["gateway_ids"] == str(gateway.id)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_validate_silo_runtime_returns_404_for_unknown_silo() -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, _ = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post("/api/v1/silos/missing/runtime/validate")

        assert response.status_code == 404
        assert "Silo not found" in response.json()["detail"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_validate_silo_runtime_returns_warnings_when_gateway_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, gateway = await _seed_org_context(session)
        board = Board(
            id=uuid4(),
            organization_id=ctx.organization.id,
            gateway_id=gateway.id,
            name="Demo Board",
            slug="demo-board",
            board_type="goal",
            objective="Demo objective",
            success_metrics={"demo": True},
        )
        session.add(board)
        await session.commit()
    app = _build_test_app(session_maker, ctx)

    original_async_client = httpx.AsyncClient

    def _mock_async_client(**kwargs: object) -> httpx.AsyncClient:
        transport = httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(
                httpx.ConnectError("All connection attempts failed", request=request)
            ),
        )
        return original_async_client(transport=transport)

    monkeypatch.setattr(
        "app.services.silos.runtime_apply.httpx.AsyncClient",
        _mock_async_client,
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            create_response = await client.post(
                "/api/v1/silos",
                json={
                    "name": "Demo Silo",
                    "blueprint_slug": "default-four-agent",
                    "gateway_assignments": [{"role_slug": "fox", "gateway_id": str(gateway.id)}],
                },
            )
            assert create_response.status_code == 201

            response = await client.post("/api/v1/silos/demo-silo/runtime/validate")

        assert response.status_code == 200
        body = response.json()
        fox = next(item for item in body["results"] if item["role_slug"] == "fox")
        assert fox["supports_picoclaw_bundle_apply"] is True
        assert fox["validated"] is None
        assert any(
            "Runtime validate failed for gateway Fox Host" in warning for warning in fox["warnings"]
        )
        assert any(
            "Runtime validate failed for gateway Fox Host" in warning
            for warning in body["warnings"]
        )
        async with session_maker() as session:
            activity = (
                await session.exec(
                    select(ActivityEvent).where(
                        ActivityEvent.event_type == "silo.runtime.validate"
                    ),
                )
            ).one()
        assert activity.board_id == board.id
        assert activity.payload is not None
        assert activity.payload["board_id"] == str(board.id)
    finally:
        await engine.dispose()
