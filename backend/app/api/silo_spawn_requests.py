"""Silo spawn request endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin, require_org_member
from app.core.time import utcnow
from app.db import crud
from app.db.session import get_session
from app.models.boards import Board
from app.models.silo_spawn_requests import SiloSpawnRequest
from app.models.silos import Silo
from app.models.tasks import Task
from app.schemas.silo_spawn_requests import (
    SiloSpawnRequestCreate,
    SiloSpawnRequestRead,
    SiloSpawnRequestUpdate,
)
from app.services.activity_log import record_activity
from app.services.organizations import OrganizationContext

router = APIRouter(prefix="/silos/spawn-requests", tags=["silos"])
SESSION_DEP = Depends(get_session)
ORG_MEMBER_DEP = Depends(require_org_member)
ORG_ADMIN_DEP = Depends(require_org_admin)


def _slugify(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed or "silo"


def _to_read(request: SiloSpawnRequest) -> SiloSpawnRequestRead:
    return SiloSpawnRequestRead.model_validate(request, from_attributes=True)


def _activity_payload(request: SiloSpawnRequest) -> dict[str, object]:
    return {
        "request_id": str(request.id),
        "request_slug": request.slug,
        "display_name": request.display_name,
        "status": request.status,
        "scope": request.scope,
        "silo_kind": request.silo_kind,
        "priority": request.priority,
        "board_id": str(request.board_id) if request.board_id else None,
        "parent_silo_id": str(request.parent_silo_id) if request.parent_silo_id else None,
        "desired_role": request.desired_role,
        "source_task_id": str(request.source_task_id) if request.source_task_id else None,
        "source_task_title": request.source_task_title,
        "runtime_preference": request.runtime_preference,
        "materialized_silo_id": str(request.materialized_silo_id)
        if request.materialized_silo_id
        else None,
        "materialized_silo_slug": request.materialized_silo_slug,
    }


async def _validate_scope_refs(
    *,
    session: AsyncSession,
    organization_id: UUID,
    board_id: UUID | None,
    parent_silo_id: UUID | None,
    source_task_id: UUID | None,
) -> Task | None:
    task: Task | None = None
    if board_id is not None:
        board = await crud.get_one_by(
            session,
            Board,
            organization_id=organization_id,
            id=board_id,
        )
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    if parent_silo_id is not None:
        silo = await crud.get_one_by(
            session,
            Silo,
            organization_id=organization_id,
            id=parent_silo_id,
        )
        if silo is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Silo not found")
    if source_task_id is not None:
        task = await session.get(Task, source_task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        if board_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="board_id is required when source_task_id is provided",
            )
        if task.board_id != board_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="source_task_id must belong to the selected board",
            )
    return task


@router.get("", response_model=list[SiloSpawnRequestRead])
async def list_silo_spawn_requests(
    board_id: UUID | None = Query(default=None),
    parent_silo_id: UUID | None = Query(default=None),
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> list[SiloSpawnRequestRead]:
    statement = (
        select(SiloSpawnRequest)
        .where(col(SiloSpawnRequest.organization_id) == ctx.organization.id)
        .order_by(col(SiloSpawnRequest.updated_at).desc())
    )
    if board_id is not None:
        statement = statement.where(col(SiloSpawnRequest.board_id) == board_id)
    if parent_silo_id is not None:
        statement = statement.where(col(SiloSpawnRequest.parent_silo_id) == parent_silo_id)
    rows = list(await session.exec(statement))
    return [_to_read(row) for row in rows]


@router.post("", response_model=SiloSpawnRequestRead, status_code=status.HTTP_201_CREATED)
async def create_silo_spawn_request(
    payload: SiloSpawnRequestCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SiloSpawnRequestRead:
    task = await _validate_scope_refs(
        session=session,
        organization_id=ctx.organization.id,
        board_id=payload.board_id,
        parent_silo_id=payload.parent_silo_id,
        source_task_id=payload.source_task_id,
    )
    now = utcnow()
    base_slug = _slugify(payload.display_name)
    slug = base_slug
    counter = 2
    while (
        await crud.get_one_by(
            session,
            SiloSpawnRequest,
            organization_id=ctx.organization.id,
            slug=slug,
        )
    ) is not None:
        slug = f"{base_slug}-{counter}"
        counter += 1

    request = SiloSpawnRequest(
        organization_id=ctx.organization.id,
        board_id=payload.board_id,
        parent_silo_id=payload.parent_silo_id,
        requested_by_user_id=ctx.member.user_id,
        slug=slug,
        display_name=payload.display_name,
        silo_kind=payload.silo_kind or "agent",
        scope=payload.scope,
        priority=payload.priority,
        desired_role=payload.desired_role,
        source_task_id=payload.source_task_id,
        source_task_title=payload.source_task_title or (task.title if task else None),
        runtime_preference=payload.runtime_preference,
        summary=payload.summary,
        desired_state=payload.desired_state,
        status="requested",
        created_at=now,
        updated_at=now,
    )
    session.add(request)
    record_activity(
        session,
        event_type="silo.request.created",
        message=f"Silo request created: {request.display_name}.",
        payload=_activity_payload(request),
        board_id=request.board_id,
    )
    await session.commit()
    await session.refresh(request)
    return _to_read(request)


@router.get("/{request_id}", response_model=SiloSpawnRequestRead)
async def get_silo_spawn_request(
    request_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> SiloSpawnRequestRead:
    request = await crud.get_one_by(
        session,
        SiloSpawnRequest,
        organization_id=ctx.organization.id,
        id=request_id,
    )
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Silo spawn request not found",
        )
    return _to_read(request)


@router.patch("/{request_id}", response_model=SiloSpawnRequestRead)
async def update_silo_spawn_request(
    request_id: UUID,
    payload: SiloSpawnRequestUpdate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SiloSpawnRequestRead:
    request = await crud.get_one_by(
        session,
        SiloSpawnRequest,
        organization_id=ctx.organization.id,
        id=request_id,
    )
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Silo spawn request not found",
        )
    if payload.status is not None:
        previous_status = request.status
        request.status = payload.status
        if previous_status != request.status:
            record_activity(
                session,
                event_type=f"silo.request.{request.status}",
                message=f"Silo request moved to {request.status}: {request.display_name}.",
                payload={
                    **_activity_payload(request),
                    "previous_status": previous_status,
                },
                board_id=request.board_id,
            )
    if payload.priority is not None:
        request.priority = payload.priority
    if payload.summary is not None:
        request.summary = payload.summary
    if payload.desired_state is not None:
        request.desired_state = payload.desired_state
    if payload.source_task_title is not None:
        request.source_task_title = payload.source_task_title
    request.updated_at = utcnow()
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return _to_read(request)
