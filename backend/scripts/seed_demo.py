"""Seed a local demo dataset for operator-driven silo/runtime E2E flows."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from sqlmodel import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

DEMO_ORGANIZATION_NAME = "Demo Organization"
DEMO_USER_EMAIL = "admin@home.local"
DEMO_USER_NAME = "Local User"
DEMO_LOCAL_AUTH_USER_ID = "local-auth-user"
DEMO_GATEWAY_NAME = "Demo Gateway"
DEMO_BOARD_NAME = "Demo Board"
DEMO_BOARD_SLUG = "demo-board"
DEMO_SILO_NAME = "Demo Silo"
DEMO_SILO_SLUG = "demo-silo"
DEMO_TASK_TITLE = "Ship silo runtime E2E flow"
DEMO_TASK_DESCRIPTION = (
    "Validate runtime bundles, open the board live feed, and dispatch a "
    "Symphony-backed execution run."
)


async def run() -> None:
    """Populate a local database with demo control-plane records."""
    from app.db.session import async_session_maker, init_db
    from app.models.agents import Agent
    from app.models.boards import Board
    from app.models.gateways import Gateway
    from app.models.organization_members import OrganizationMember
    from app.models.organizations import Organization
    from app.models.silos import Silo
    from app.models.silo_roles import SiloRole
    from app.models.tasks import Task
    from app.models.users import User
    from app.schemas.silos import SiloCreate, SiloGatewayAssignment, SiloUpdate
    from app.services.silos import SiloService

    await init_db()
    async with async_session_maker() as session:
        demo_workspace_root = BACKEND_ROOT / ".tmp" / "openclaw-demo"
        demo_workspace_root.mkdir(parents=True, exist_ok=True)

        organization = (
            await session.exec(
                select(Organization).where(Organization.name == DEMO_ORGANIZATION_NAME),
            )
        ).first()
        if organization is None:
            organization = Organization(name=DEMO_ORGANIZATION_NAME)
            session.add(organization)
            await session.commit()
            await session.refresh(organization)

        user = (
            await session.exec(
                select(User).where(User.clerk_user_id == DEMO_LOCAL_AUTH_USER_ID),
            )
        ).first()
        if user is None:
            user = User(
                clerk_user_id=DEMO_LOCAL_AUTH_USER_ID,
                email=DEMO_USER_EMAIL,
                name=DEMO_USER_NAME,
                is_super_admin=True,
                active_organization_id=organization.id,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            changed = False
            if user.email != DEMO_USER_EMAIL:
                user.email = DEMO_USER_EMAIL
                changed = True
            if user.name != DEMO_USER_NAME:
                user.name = DEMO_USER_NAME
                changed = True
            if not user.is_super_admin:
                user.is_super_admin = True
                changed = True
            if user.active_organization_id != organization.id:
                user.active_organization_id = organization.id
                changed = True
            if changed:
                session.add(user)
                await session.commit()

        membership = (
            await session.exec(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == organization.id,
                    OrganizationMember.user_id == user.id,
                ),
            )
        ).first()
        if membership is None:
            membership = OrganizationMember(
                organization_id=organization.id,
                user_id=user.id,
                role="owner",
                all_boards_read=True,
                all_boards_write=True,
            )
            session.add(membership)
            await session.commit()
        else:
            changed = False
            if membership.role != "owner":
                membership.role = "owner"
                changed = True
            if not membership.all_boards_read:
                membership.all_boards_read = True
                changed = True
            if not membership.all_boards_write:
                membership.all_boards_write = True
                changed = True
            if changed:
                session.add(membership)
                await session.commit()

        gateway = (
            await session.exec(
                select(Gateway).where(
                    Gateway.organization_id == organization.id,
                    Gateway.name == DEMO_GATEWAY_NAME,
                ),
            )
        ).first()
        if gateway is None:
            gateway = Gateway(
                organization_id=organization.id,
                name=DEMO_GATEWAY_NAME,
                url="http://localhost:8080",
                token=None,
                workspace_root=str(demo_workspace_root),
            )
            session.add(gateway)
            await session.commit()
            await session.refresh(gateway)
        else:
            changed = False
            if gateway.workspace_root != str(demo_workspace_root):
                gateway.workspace_root = str(demo_workspace_root)
                changed = True
            if gateway.url != "http://localhost:8080":
                gateway.url = "http://localhost:8080"
                changed = True
            if changed:
                session.add(gateway)
                await session.commit()

        board = (
            await session.exec(
                select(Board).where(
                    Board.organization_id == organization.id,
                    Board.slug == DEMO_BOARD_SLUG,
                ),
            )
        ).first()
        if board is None:
            board = Board(
                organization_id=organization.id,
                name=DEMO_BOARD_NAME,
                slug=DEMO_BOARD_SLUG,
                gateway_id=gateway.id,
                board_type="goal",
                objective="Demo objective",
                success_metrics={"demo": True, "silo_runtime": "validated"},
            )
            session.add(board)
            await session.commit()
            await session.refresh(board)
        elif board.gateway_id != gateway.id:
            board.gateway_id = gateway.id
            session.add(board)
            await session.commit()

        lead = (
            await session.exec(
                select(Agent).where(
                    Agent.board_id == board.id,
                    Agent.is_board_lead.is_(True),
                ),
            )
        ).first()
        if lead is None:
            lead = Agent(
                board_id=board.id,
                gateway_id=gateway.id,
                name="Lead Agent",
                status="online",
                is_board_lead=True,
            )
            session.add(lead)
            await session.commit()
            await session.refresh(lead)
        else:
            changed = False
            if lead.gateway_id != gateway.id:
                lead.gateway_id = gateway.id
                changed = True
            if lead.status != "online":
                lead.status = "online"
                changed = True
            if not lead.is_board_lead:
                lead.is_board_lead = True
                changed = True
            if changed:
                session.add(lead)
                await session.commit()

        task = (
            await session.exec(
                select(Task).where(
                    Task.board_id == board.id,
                    Task.title == DEMO_TASK_TITLE,
                ),
            )
        ).first()
        if task is None:
            task = Task(
                board_id=board.id,
                title=DEMO_TASK_TITLE,
                description=DEMO_TASK_DESCRIPTION,
                status="inbox",
                priority="high",
                created_by_user_id=user.id,
                assigned_agent_id=lead.id,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
        else:
            changed = False
            if task.description != DEMO_TASK_DESCRIPTION:
                task.description = DEMO_TASK_DESCRIPTION
                changed = True
            if task.assigned_agent_id != lead.id:
                task.assigned_agent_id = lead.id
                changed = True
            if task.created_by_user_id != user.id:
                task.created_by_user_id = user.id
                changed = True
            if task.priority != "high":
                task.priority = "high"
                changed = True
            if changed:
                session.add(task)
                await session.commit()

        assignments = [
            SiloGatewayAssignment(
                role_slug=role_slug,
                gateway_id=str(gateway.id),
                workspace_root=str(demo_workspace_root / role_slug),
            )
            for role_slug in ("fox", "bunny", "owl", "otter")
        ]

        silo_service = SiloService(session)
        silo = (
            await session.exec(
                select(Silo).where(
                    Silo.organization_id == organization.id,
                    Silo.slug == DEMO_SILO_SLUG,
                ),
            )
        ).first()
        if silo is None:
            await silo_service.create_silo(
                organization_id=organization.id,
                payload=SiloCreate(
                    name=DEMO_SILO_NAME,
                    blueprint_slug="default-four-agent",
                    owner_display_name=user.name,
                    enable_symphony=True,
                    enable_telemetry=True,
                    gateway_assignments=assignments,
                ),
            )
        else:
            await silo_service.update_silo(
                organization_id=organization.id,
                slug=silo.slug,
                payload=SiloUpdate(
                    enable_symphony=True,
                    enable_telemetry=True,
                    gateway_assignments=assignments,
                ),
            )

        refreshed_silo = (
            await session.exec(
                select(Silo).where(
                    Silo.organization_id == organization.id,
                    Silo.slug == DEMO_SILO_SLUG,
                ),
            )
        ).first()
        role_rows = []
        if refreshed_silo is not None:
            role_rows = (
                await session.exec(
                    select(SiloRole)
                    .where(SiloRole.silo_id == refreshed_silo.id)
                    .order_by(SiloRole.created_at.asc()),
                )
            ).all()

        print("Seed complete")
        print(f"Organization: {organization.name} ({organization.id})")
        print(f"User: {user.email} ({user.id})")
        print(f"Gateway: {gateway.name} ({gateway.id})")
        print(f"Board: {board.name} ({board.id})")
        print(f"Lead agent: {lead.name} ({lead.id})")
        print(f"Task: {task.title} ({task.id})")
        if refreshed_silo is not None:
            print(
                "Silo: "
                f"{refreshed_silo.name} ({refreshed_silo.slug}) "
                f"symphony={refreshed_silo.enable_symphony} "
                f"telemetry={refreshed_silo.enable_telemetry}",
            )
        if role_rows:
            print("Silo roles:")
            for role in role_rows:
                print(
                    f"  - {role.slug}: runtime={role.runtime_kind} "
                    f"gateway={role.gateway_name or 'none'} "
                    f"workspace={role.workspace_root or 'none'}",
                )


if __name__ == "__main__":
    asyncio.run(run())
