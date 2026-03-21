"""Runtime orchestration APIs for persisted silos."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_org_admin
from app.db.session import get_session
from app.schemas.silos import SiloRuntimeOperationResponseRead
from app.services.organizations import OrganizationContext
from app.services.silos import SiloRuntimeOrchestrator, SiloService

router = APIRouter(prefix="/silos", tags=["silos"])
SESSION_DEP = Depends(get_session)
ORG_ADMIN_DEP = Depends(require_org_admin)


@router.post("/{slug}/runtime/validate", response_model=SiloRuntimeOperationResponseRead)
async def validate_silo_runtime(
    slug: str,
    session=SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SiloRuntimeOperationResponseRead:
    """Validate all supported runtime targets for one persisted silo."""
    orchestrator = SiloRuntimeOrchestrator(silo_service=SiloService(session))
    try:
        return await orchestrator.run(
            organization_id=ctx.organization.id,
            slug=slug,
            mode="validate",
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/{slug}/runtime/apply", response_model=SiloRuntimeOperationResponseRead)
async def apply_silo_runtime(
    slug: str,
    session=SESSION_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> SiloRuntimeOperationResponseRead:
    """Apply all supported runtime targets for one persisted silo."""
    orchestrator = SiloRuntimeOrchestrator(silo_service=SiloService(session))
    try:
        return await orchestrator.run(
            organization_id=ctx.organization.id,
            slug=slug,
            mode="apply",
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
