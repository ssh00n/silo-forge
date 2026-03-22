"""Read-only silo blueprint APIs for MVP silo creation flows."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.silos import SiloBlueprintRead
from app.services.silos import SiloService

router = APIRouter(prefix="/silo-blueprints", tags=["silo-blueprints"])


@router.get("", response_model=list[SiloBlueprintRead])
async def list_silo_blueprints() -> list[SiloBlueprintRead]:
    """Return built-in silo blueprints available for MVP provisioning."""
    return SiloService().list_builtin_blueprints()


@router.get("/{blueprint_slug}", response_model=SiloBlueprintRead)
async def get_silo_blueprint(blueprint_slug: str) -> SiloBlueprintRead:
    """Return one built-in silo blueprint by slug."""
    blueprint = SiloService().get_builtin_blueprint(blueprint_slug)
    if blueprint is not None:
        return blueprint
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found")
