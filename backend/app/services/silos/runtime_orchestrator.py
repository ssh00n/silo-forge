"""Orchestration helpers for running persisted silo plans against runtimes."""

from __future__ import annotations

from uuid import UUID

from app.core.time import utcnow
from app.db import crud
from app.models.gateways import Gateway
from app.models.silo_runtime_operations import (
    SiloRuntimeOperation,
    SiloRuntimeOperationResult,
)
from app.models.silos import Silo
from app.schemas.silos import (
    SiloRead,
    SiloRuntimeOperationRead,
    SiloRuntimeOperationResponseRead,
)
from app.services.silos.provision_plan import ProvisionPlanService
from app.services.silos.runtime_apply import RuntimeApplyService
from app.services.silos.service import SiloService


class SiloRuntimeOrchestrator:
    """Validate or apply persisted silo bundles against assigned gateways."""

    def __init__(
        self,
        *,
        silo_service: SiloService,
        provision_plan_service: ProvisionPlanService | None = None,
        runtime_apply_service: RuntimeApplyService | None = None,
    ) -> None:
        self._silo_service = silo_service
        self._provision_plan_service = provision_plan_service or ProvisionPlanService(silo_service)
        self._runtime_apply_service = runtime_apply_service or RuntimeApplyService()

    async def run(
        self,
        *,
        organization_id: UUID,
        slug: str,
        mode: str,
    ) -> SiloRuntimeOperationResponseRead:
        """Run validate/apply for a persisted silo."""
        silo = await self._silo_service.get_silo(organization_id=organization_id, slug=slug)
        if silo is None:
            raise ValueError(f"Silo not found: {slug}")

        plan = await self._provision_plan_service.build_plan_for_silo(
            organization_id=organization_id,
            slug=slug,
        )
        session = self._silo_service._session
        if session is None:
            raise RuntimeError("SiloRuntimeOrchestrator requires a database session")
        silo_row = await crud.get_one_by(
            session,
            Silo,
            organization_id=organization_id,
            slug=slug,
        )
        if silo_row is None:
            raise ValueError(f"Silo not found: {slug}")

        results: list[SiloRuntimeOperationRead] = []
        warnings = list(plan.warnings)
        for target in plan.targets:
            target_warnings = list(target.warnings)
            if not target.supports_picoclaw_bundle_apply or target.bundle is None:
                results.append(
                    SiloRuntimeOperationRead(
                        role_slug=target.role_slug,
                        runtime_kind=target.runtime_kind,
                        gateway_name=target.gateway_name,
                        supports_picoclaw_bundle_apply=False,
                        warnings=target_warnings,
                    ),
                )
                continue

            role_state = next((role for role in plan.preview.roles if role.slug == target.role_slug), None)
            if role_state is None or not role_state.gateway_id:
                target_warnings.append("No gateway assignment is stored for this role.")
                results.append(
                    SiloRuntimeOperationRead(
                        role_slug=target.role_slug,
                        runtime_kind=target.runtime_kind,
                        gateway_name=target.gateway_name,
                        supports_picoclaw_bundle_apply=False,
                        warnings=target_warnings,
                    ),
                )
                continue

            gateway = await crud.get_one_by(
                session,
                Gateway,
                organization_id=organization_id,
                id=UUID(role_state.gateway_id),
            )
            if gateway is None:
                raise ValueError(
                    f"Gateway not found for role {target.role_slug}: {role_state.gateway_id}",
                )

            if mode == "validate":
                validated = await self._runtime_apply_service.validate_bundle(
                    runtime_url=gateway.url,
                    runtime_token=gateway.token,
                    allow_insecure_tls=gateway.allow_insecure_tls,
                    bundle=target.bundle,
                )
                target_warnings.extend(validated.warnings)
                results.append(
                    SiloRuntimeOperationRead(
                        role_slug=target.role_slug,
                        runtime_kind=target.runtime_kind,
                        gateway_name=target.gateway_name,
                        supports_picoclaw_bundle_apply=True,
                        validated=validated,
                        warnings=target_warnings,
                    ),
                )
                continue

            applied = await self._runtime_apply_service.apply_bundle(
                runtime_url=gateway.url,
                runtime_token=gateway.token,
                allow_insecure_tls=gateway.allow_insecure_tls,
                bundle=target.bundle,
            )
            target_warnings.extend(applied.warnings)
            results.append(
                SiloRuntimeOperationRead(
                    role_slug=target.role_slug,
                    runtime_kind=target.runtime_kind,
                    gateway_name=target.gateway_name,
                    supports_picoclaw_bundle_apply=True,
                    applied=applied,
                    warnings=target_warnings,
                ),
            )

        response = SiloRuntimeOperationResponseRead(
            silo=silo,
            mode="apply" if mode == "apply" else "validate",
            results=results,
            warnings=warnings,
        )
        await self._persist_operation(
            silo_id=silo_row.id,
            response=response,
        )
        return response

    async def _persist_operation(
        self,
        *,
        silo_id: UUID,
        response: SiloRuntimeOperationResponseRead,
    ) -> None:
        session = self._silo_service._session
        if session is None:
            raise RuntimeError("SiloRuntimeOrchestrator requires a database session")

        now = utcnow()
        operation = SiloRuntimeOperation(
            silo_id=silo_id,
            mode=response.mode,
            warnings=list(response.warnings),
            created_at=now,
            updated_at=now,
        )
        session.add(operation)
        await session.flush()

        for result in response.results:
            session.add(
                SiloRuntimeOperationResult(
                    operation_id=operation.id,
                    role_slug=result.role_slug,
                    runtime_kind=result.runtime_kind,
                    gateway_name=result.gateway_name,
                    supports_picoclaw_bundle_apply=result.supports_picoclaw_bundle_apply,
                    validated=result.validated.model_dump(mode="json")
                    if result.validated is not None
                    else None,
                    applied=result.applied.model_dump(mode="json")
                    if result.applied is not None
                    else None,
                    warnings=list(result.warnings),
                    created_at=now,
                    updated_at=now,
                ),
            )
        await session.commit()
