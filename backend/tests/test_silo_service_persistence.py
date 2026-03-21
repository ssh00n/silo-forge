# ruff: noqa: INP001
"""Persistence tests for silo service and gateway assignments."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.silo_roles import SiloRole
from app.schemas.silos import SiloCreate
from app.services.silos.service import SiloService


@pytest.mark.asyncio
async def test_create_silo_persists_roles_and_gateway_assignment() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        org = Organization(id=uuid4(), name="Personal")
        gateway = Gateway(
            id=uuid4(),
            organization_id=org.id,
            name="Fox Host",
            url="http://gateway.local",
            workspace_root="/srv/openclaw",
        )
        session.add(org)
        session.add(gateway)
        await session.commit()

        service = SiloService(session)
        silo = await service.create_silo(
            organization_id=org.id,
            payload=SiloCreate(
                name="Demo Silo",
                blueprint_slug="default-four-agent",
                gateway_assignments=[
                    {
                        "role_slug": "fox",
                        "gateway_id": str(gateway.id),
                        "workspace_root": "/srv/fox",
                    },
                ],
            ),
        )

        assert silo.slug == "demo-silo"
        assert silo.role_count == 4

        roles = list(await session.exec(select(SiloRole).where(SiloRole.slug == "fox")))
        assert len(roles) == 1
        assert roles[0].gateway_id == gateway.id
        assert roles[0].gateway_name == "Fox Host"
        assert roles[0].workspace_root == "/srv/fox"

    await engine.dispose()


@pytest.mark.asyncio
async def test_list_and_get_silos_return_persisted_summary() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        org = Organization(id=uuid4(), name="Personal")
        session.add(org)
        await session.commit()

        service = SiloService(session)
        await service.create_silo(
            organization_id=org.id,
            payload=SiloCreate(name="Demo Silo", blueprint_slug="default-four-agent"),
        )

        listed = await service.list_silos(organization_id=org.id)
        loaded = await service.get_silo(organization_id=org.id, slug="demo-silo")

        assert len(listed) == 1
        assert listed[0].slug == "demo-silo"
        assert loaded is not None
        assert loaded.role_count == 4

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_silo_rejects_unknown_gateway_assignment() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        org = Organization(id=uuid4(), name="Personal")
        session.add(org)
        await session.commit()

        service = SiloService(session)
        with pytest.raises(ValueError, match="Unknown gateway id"):
            await service.create_silo(
                organization_id=org.id,
                payload=SiloCreate(
                    name="Broken Silo",
                    blueprint_slug="default-four-agent",
                    gateway_assignments=[
                        {
                            "role_slug": "fox",
                            "gateway_id": str(uuid4()),
                        },
                    ],
                ),
            )

    await engine.dispose()
