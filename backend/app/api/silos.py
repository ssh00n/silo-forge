"""Silo preview APIs for MVP desired-state creation flows."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.db.session import get_session
from app.schemas.silos import (
    SiloCreate,
    SiloDetailRead,
    SiloPreviewRead,
    SiloRead,
    SiloUpdate,
)
from app.services.organizations import OrganizationContext
from app.services.silos import SiloService

router = APIRouter(prefix="/silos", tags=["silos"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)


@router.get("", response_model=list[SiloRead])
async def list_silos(
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> list[SiloRead]:
    """List persisted silos for the caller's organization."""
    service = SiloService(session)
    return await service.list_silos(organization_id=ctx.organization.id)


@router.get("/{slug}", response_model=SiloRead)
async def get_silo(
    slug: str,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SiloRead:
    """Return one persisted silo by slug for the caller's organization."""
    service = SiloService(session)
    silo = await service.get_silo(organization_id=ctx.organization.id, slug=slug)
    if silo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Silo not found")
    return silo


@router.get("/{slug}/detail", response_model=SiloDetailRead)
async def get_silo_detail(
    slug: str,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SiloDetailRead:
    """Return one persisted silo with detail data for operator views."""
    service = SiloService(session)
    silo = await service.get_silo_detail(organization_id=ctx.organization.id, slug=slug)
    if silo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Silo not found")
    return silo


@router.post("", response_model=SiloRead, status_code=status.HTTP_201_CREATED)
async def create_silo(
    payload: SiloCreate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SiloRead:
    """Persist a new silo and its resolved role assignments."""
    service = SiloService(session)
    try:
        return await service.create_silo(organization_id=ctx.organization.id, payload=payload)
    except ValueError as exc:
        message = str(exc)
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        if message.startswith("Unknown blueprint") or message.startswith("Unknown gateway id"):
            status_code = status.HTTP_404_NOT_FOUND
        if message.startswith("Silo already exists"):
            status_code = status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.patch("/{slug}", response_model=SiloDetailRead)
async def update_silo(
    slug: str,
    payload: SiloUpdate,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SiloDetailRead:
    """Patch one persisted silo and return the refreshed detail payload."""
    service = SiloService(session)
    try:
        return await service.update_silo(
            organization_id=ctx.organization.id,
            slug=slug,
            payload=payload,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        if message == "Silo not found" or message.startswith("Unknown gateway id"):
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.post("/preview", response_model=SiloPreviewRead)
async def preview_silo(payload: SiloCreate) -> SiloPreviewRead:
    """Build a desired-state silo preview from a create payload."""
    service = SiloService()
    try:
        return service.build_preview(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
