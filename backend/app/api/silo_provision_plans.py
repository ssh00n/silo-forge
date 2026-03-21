"""Provision-plan preview APIs for silo runtime rollout preparation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.silos import SiloCreate, SiloProvisionPlanRead
from app.services.silos import ProvisionPlanService

router = APIRouter(prefix="/silo-provision-plans", tags=["silo-provision-plans"])


@router.post("/preview", response_model=SiloProvisionPlanRead)
async def preview_silo_provision_plan(payload: SiloCreate) -> SiloProvisionPlanRead:
    """Render a provision plan preview for the given silo create payload."""
    service = ProvisionPlanService()
    try:
        return service.build_plan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
