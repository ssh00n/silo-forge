"""Orchestration helpers for running persisted silo plans against runtimes."""

from __future__ import annotations

from uuid import UUID

import httpx

from app.core.time import utcnow
from app.db import crud
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.silo_runtime_operations import (
    SiloRuntimeOperation,
    SiloRuntimeOperationResult,
)
from app.models.silos import Silo
from app.schemas.silos import (
    SiloRuntimeOperationRead,
    SiloRuntimeOperationResponseRead,
)
from app.contracts.activity import finalize_silo_runtime_activity_payload
from app.services.activity_log import record_activity
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
        applied_gateway_ids: set[str] = set()
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

            role_state = next(
                (role for role in plan.preview.roles if role.slug == target.role_slug), None
            )
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
            applied_gateway_ids.add(str(gateway.id))

            if mode == "validate":
                try:
                    validated = await self._runtime_apply_service.validate_bundle(
                        runtime_url=gateway.url,
                        runtime_token=gateway.token,
                        allow_insecure_tls=gateway.allow_insecure_tls,
                        bundle=target.bundle,
                    )
                    target_warnings.extend(validated.warnings)
                except httpx.HTTPError as exc:
                    warning = f"Runtime validate failed for gateway {gateway.name}: {exc!s}"
                    target_warnings.append(warning)
                    warnings.append(warning)
                    results.append(
                        SiloRuntimeOperationRead(
                            role_slug=target.role_slug,
                            runtime_kind=target.runtime_kind,
                            gateway_name=target.gateway_name,
                            supports_picoclaw_bundle_apply=True,
                            warnings=target_warnings,
                        ),
                    )
                    continue
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

            try:
                applied = await self._runtime_apply_service.apply_bundle(
                    runtime_url=gateway.url,
                    runtime_token=gateway.token,
                    allow_insecure_tls=gateway.allow_insecure_tls,
                    bundle=target.bundle,
                )
                target_warnings.extend(applied.warnings)
            except httpx.HTTPError as exc:
                warning = f"Runtime apply failed for gateway {gateway.name}: {exc!s}"
                target_warnings.append(warning)
                warnings.append(warning)
                results.append(
                    SiloRuntimeOperationRead(
                        role_slug=target.role_slug,
                        runtime_kind=target.runtime_kind,
                        gateway_name=target.gateway_name,
                        supports_picoclaw_bundle_apply=True,
                        warnings=target_warnings,
                    ),
                )
                continue
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
            gateway_ids=sorted(applied_gateway_ids),
        )
        return response

    async def _persist_operation(
        self,
        *,
        silo_id: UUID,
        response: SiloRuntimeOperationResponseRead,
        gateway_ids: list[str],
    ) -> None:
        session = self._silo_service._session
        if session is None:
            raise RuntimeError("SiloRuntimeOrchestrator requires a database session")
        silo_row = await session.get(Silo, silo_id)
        if silo_row is None:
            raise ValueError(f"Silo not found: {silo_id}")

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
        restart_required = any(
            bool(result.validated and result.validated.restart_required)
            or bool(result.applied and result.applied.restart_required)
            for result in response.results
        )
        gateway_names = sorted(
            {
                result.gateway_name
                for result in response.results
                if result.gateway_name is not None and result.gateway_name.strip()
            },
        )
        board_id: UUID | None = None
        for gateway_id in gateway_ids:
            board = await crud.get_one_by(
                session,
                Board,
                organization_id=silo_row.organization_id,
                gateway_id=UUID(gateway_id),
            )
            if board is not None:
                board_id = board.id
                break
        record_activity(
            session,
            event_type=f"silo.runtime.{response.mode}",
            message=(
                f"{'Validated' if response.mode == 'validate' else 'Applied'} runtime bundle plan for "
                f"{response.silo.name}."
            ),
            payload=finalize_silo_runtime_activity_payload(
                {
                    "silo_id": str(silo_id),
                    "silo_slug": response.silo.slug,
                    "silo_name": response.silo.name,
                    "board_id": str(board_id) if board_id is not None else None,
                    "mode": response.mode,
                    "operation_id": str(operation.id),
                    "result_count": str(len(response.results)),
                    "warning_count": str(len(response.warnings)),
                    "restart_required": "yes" if restart_required else "no",
                    "gateway_names": ", ".join(gateway_names),
                    "gateway_ids": ", ".join(gateway_ids),
                    "roles": ", ".join(result.role_slug for result in response.results),
                }
            ),
            board_id=board_id,
        )
        await session.commit()
