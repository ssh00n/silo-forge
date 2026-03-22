"""Silo desired-state preview service for MVP provisioning flows."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import asc, desc
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.db import crud
from app.models.gateways import Gateway
from app.models.silo_roles import SiloRole
from app.models.silo_runtime_operations import (
    SiloRuntimeOperation,
    SiloRuntimeOperationResult,
)
from app.models.silos import Silo
from app.schemas.silos import (
    RuntimeBundleApplyResponseRead,
    RuntimeBundleValidateResponseRead,
    SiloBlueprintRead,
    SiloCreate,
    SiloDetailRead,
    SiloGatewayAssignment,
    SiloPreviewRead,
    SiloRead,
    SiloRoleDesiredState,
    SiloRuntimeHistoryEntryRead,
    SiloRuntimeOperationRead,
    SiloUpdate,
)
from app.services.silos.blueprints import build_default_four_agent_blueprint

_SLUG_SANITIZER_RE = re.compile(r"[^a-z0-9]+")


class SiloService:
    """Build desired-state silo previews from built-in blueprints."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    def list_builtin_blueprints(self) -> list[SiloBlueprintRead]:
        """Return built-in blueprints available for preview flows."""
        return [build_default_four_agent_blueprint()]

    def get_builtin_blueprint(self, blueprint_slug: str) -> SiloBlueprintRead | None:
        """Look up a built-in blueprint by slug."""
        normalized = blueprint_slug.strip()
        for blueprint in self.list_builtin_blueprints():
            if blueprint.slug == normalized:
                return blueprint
        return None

    def build_preview(self, payload: SiloCreate) -> SiloPreviewRead:
        """Build a desired-state preview for a silo create request."""
        blueprint = self.get_builtin_blueprint(payload.blueprint_slug)
        if blueprint is None:
            raise ValueError(f"Unknown blueprint: {payload.blueprint_slug}")

        enable_symphony = payload.enable_symphony and blueprint.supports_symphony
        enable_telemetry = payload.enable_telemetry and blueprint.supports_telemetry
        warnings: list[str] = []

        if payload.enable_symphony and not blueprint.supports_symphony:
            warnings.append(
                f"Blueprint {blueprint.slug} does not support Symphony; ignoring enable_symphony.",
            )
        if payload.enable_telemetry and not blueprint.supports_telemetry:
            warnings.append(
                f"Blueprint {blueprint.slug} does not support telemetry; ignoring enable_telemetry.",
            )

        target_by_role = {target.role_slug: target for target in blueprint.provision_targets}
        assignment_by_role = self._assignment_map(payload.gateway_assignments)
        roles: list[SiloRoleDesiredState] = []
        for role in blueprint.roles:
            if role.runtime_kind == "symphony" and not enable_symphony:
                warnings.append(f"Skipping optional role {role.slug} because Symphony is disabled.")
                continue

            target = target_by_role.get(role.slug)
            assignment = assignment_by_role.get(role.slug)
            gateway_id = assignment.gateway_id if assignment else None
            roles.append(
                SiloRoleDesiredState(
                    slug=role.slug,
                    display_name=role.display_name,
                    role_type=role.role_type,
                    runtime_kind=role.runtime_kind,
                    host_kind=role.host_kind,
                    default_model=role.default_model,
                    fallback_model=role.fallback_model,
                    channel_name=role.channel_name,
                    gateway_id=gateway_id,
                    gateway_name=target.gateway_name if target else None,
                    workspace_root=assignment.workspace_root
                    if assignment and assignment.workspace_root
                    else (target.workspace_root if target else None),
                    secret_bindings=list(role.secret_bindings),
                ),
            )

        return SiloPreviewRead(
            slug=_slugify(payload.name),
            name=payload.name,
            blueprint_slug=blueprint.slug,
            blueprint_version=payload.blueprint_version or blueprint.version,
            enable_symphony=enable_symphony,
            enable_telemetry=enable_telemetry,
            roles=roles,
            shared_secret_bindings=list(blueprint.shared_secret_bindings),
            warnings=warnings,
        )

    async def create_silo(self, *, organization_id: UUID, payload: SiloCreate) -> SiloRead:
        """Persist a silo and its resolved role assignments."""
        if self._session is None:
            raise RuntimeError("SiloService.create_silo requires a database session")

        preview = self.build_preview(payload)
        existing = await crud.get_one_by(
            self._session,
            Silo,
            organization_id=organization_id,
            slug=preview.slug,
        )
        if existing is not None:
            raise ValueError(f"Silo already exists: {preview.slug}")

        now = utcnow()
        silo = Silo(
            organization_id=organization_id,
            slug=preview.slug,
            name=preview.name,
            blueprint_slug=preview.blueprint_slug,
            blueprint_version=preview.blueprint_version,
            owner_display_name=payload.owner_display_name,
            status="draft",
            enable_symphony=preview.enable_symphony,
            enable_telemetry=preview.enable_telemetry,
            desired_state=preview.model_dump(mode="json"),
            created_at=now,
            updated_at=now,
        )
        self._session.add(silo)
        await self._session.flush()

        for role in preview.roles:
            gateway_name = role.gateway_name
            gateway_id = UUID(role.gateway_id) if role.gateway_id else None
            if gateway_id is not None:
                gateway = await self._session.get(Gateway, gateway_id)
                if gateway is None:
                    raise ValueError(f"Unknown gateway id for role {role.slug}: {gateway_id}")
                gateway_name = gateway.name
            self._session.add(
                SiloRole(
                    silo_id=silo.id,
                    slug=role.slug,
                    display_name=role.display_name,
                    role_type=role.role_type,
                    runtime_kind=role.runtime_kind,
                    host_kind=role.host_kind,
                    default_model=role.default_model,
                    fallback_model=role.fallback_model,
                    channel_name=role.channel_name,
                    gateway_id=gateway_id,
                    gateway_name=gateway_name,
                    workspace_root=role.workspace_root,
                    secret_bindings=[
                        binding.model_dump(mode="json") for binding in role.secret_bindings
                    ],
                    created_at=now,
                    updated_at=now,
                ),
            )

        await self._session.commit()
        return SiloRead(
            slug=silo.slug,
            name=silo.name,
            blueprint_slug=silo.blueprint_slug,
            blueprint_version=silo.blueprint_version,
            status=silo.status,
            enable_symphony=silo.enable_symphony,
            enable_telemetry=silo.enable_telemetry,
            role_count=len(preview.roles),
        )

    async def update_silo(
        self,
        *,
        organization_id: UUID,
        slug: str,
        payload: SiloUpdate,
    ) -> SiloDetailRead:
        """Patch persisted silo assignment and toggle data."""
        if self._session is None:
            raise RuntimeError("SiloService.update_silo requires a database session")

        silo = await crud.get_one_by(
            self._session,
            Silo,
            organization_id=organization_id,
            slug=slug,
        )
        if silo is None:
            raise ValueError("Silo not found")

        desired_state = SiloPreviewRead.model_validate(silo.desired_state or {})
        assignment_by_role = self._assignment_map(payload.gateway_assignments)
        role_rows = await crud.list_by(self._session, SiloRole, silo_id=silo.id)
        role_by_slug = {role.slug: role for role in role_rows}

        if payload.enable_symphony is not None:
            silo.enable_symphony = payload.enable_symphony
            desired_state.enable_symphony = payload.enable_symphony
        if payload.enable_telemetry is not None:
            silo.enable_telemetry = payload.enable_telemetry
            desired_state.enable_telemetry = payload.enable_telemetry

        now = utcnow()
        for role_slug, assignment in assignment_by_role.items():
            role = role_by_slug.get(role_slug)
            if role is None:
                raise ValueError(f"Unknown silo role: {role_slug}")
            gateway_id = UUID(assignment.gateway_id) if assignment.gateway_id else None
            gateway_name: str | None = None
            if gateway_id is not None:
                gateway = await self._session.get(Gateway, gateway_id)
                if gateway is None:
                    raise ValueError(f"Unknown gateway id for role {role_slug}: {gateway_id}")
                gateway_name = gateway.name

            role.gateway_id = gateway_id
            role.gateway_name = gateway_name
            if assignment.workspace_root is not None:
                role.workspace_root = assignment.workspace_root or None
            role.updated_at = now
            self._session.add(role)

            for desired_role in desired_state.roles:
                if desired_role.slug != role_slug:
                    continue
                desired_role.gateway_id = str(gateway_id) if gateway_id else None
                desired_role.gateway_name = gateway_name
                if assignment.workspace_root is not None:
                    desired_role.workspace_root = assignment.workspace_root or None
                break

        silo.desired_state = desired_state.model_dump(mode="json")
        silo.updated_at = now
        self._session.add(silo)
        await self._session.commit()

        detail = await self.get_silo_detail(organization_id=organization_id, slug=slug)
        if detail is None:
            raise ValueError("Silo not found")
        return detail

    async def list_silos(self, *, organization_id: UUID) -> list[SiloRead]:
        """List persisted silos for one organization."""
        if self._session is None:
            raise RuntimeError("SiloService.list_silos requires a database session")

        silos = await crud.list_by(
            self._session,
            Silo,
            organization_id=organization_id,
        )
        results: list[SiloRead] = []
        for silo in silos:
            roles = await crud.list_by(self._session, SiloRole, silo_id=silo.id)
            results.append(
                SiloRead(
                    slug=silo.slug,
                    name=silo.name,
                    blueprint_slug=silo.blueprint_slug,
                    blueprint_version=silo.blueprint_version,
                    status=silo.status,
                    enable_symphony=silo.enable_symphony,
                    enable_telemetry=silo.enable_telemetry,
                    role_count=len(roles),
                ),
            )
        return results

    async def get_silo(self, *, organization_id: UUID, slug: str) -> SiloRead | None:
        """Fetch one persisted silo by organization and slug."""
        if self._session is None:
            raise RuntimeError("SiloService.get_silo requires a database session")

        silo = await crud.get_one_by(
            self._session,
            Silo,
            organization_id=organization_id,
            slug=slug,
        )
        if silo is None:
            return None
        roles = await crud.list_by(self._session, SiloRole, silo_id=silo.id)
        return SiloRead(
            slug=silo.slug,
            name=silo.name,
            blueprint_slug=silo.blueprint_slug,
            blueprint_version=silo.blueprint_version,
            status=silo.status,
            enable_symphony=silo.enable_symphony,
            enable_telemetry=silo.enable_telemetry,
            role_count=len(roles),
        )

    async def get_silo_detail(self, *, organization_id: UUID, slug: str) -> SiloDetailRead | None:
        """Fetch one persisted silo with desired state, roles, and plan preview."""
        if self._session is None:
            raise RuntimeError("SiloService.get_silo_detail requires a database session")

        silo = await crud.get_one_by(
            self._session,
            Silo,
            organization_id=organization_id,
            slug=slug,
        )
        if silo is None:
            return None

        role_rows = await crud.list_by(self._session, SiloRole, silo_id=silo.id)
        roles = [
            SiloRoleDesiredState(
                slug=role.slug,
                display_name=role.display_name,
                role_type=role.role_type,
                runtime_kind=role.runtime_kind,
                host_kind=role.host_kind,
                default_model=role.default_model,
                fallback_model=role.fallback_model,
                channel_name=role.channel_name,
                gateway_id=str(role.gateway_id) if role.gateway_id else None,
                gateway_name=role.gateway_name,
                workspace_root=role.workspace_root,
                secret_bindings=list(role.secret_bindings or []),
            )
            for role in role_rows
        ]
        desired_state = SiloPreviewRead.model_validate(silo.desired_state or {})
        desired_state.roles = roles
        summary = SiloRead(
            slug=silo.slug,
            name=silo.name,
            blueprint_slug=silo.blueprint_slug,
            blueprint_version=silo.blueprint_version,
            status=silo.status,
            enable_symphony=silo.enable_symphony,
            enable_telemetry=silo.enable_telemetry,
            role_count=len(roles),
        )
        from app.services.silos.provision_plan import ProvisionPlanService

        provision_plan = await ProvisionPlanService(self).build_plan_for_silo(
            organization_id=organization_id,
            slug=slug,
        )
        latest_runtime_operation = await self._latest_runtime_operation(silo_id=silo.id)
        return SiloDetailRead(
            silo=summary,
            desired_state=desired_state,
            roles=roles,
            provision_plan=provision_plan,
            latest_runtime_operation=latest_runtime_operation,
        )

    def _assignment_map(
        self,
        assignments: list[SiloGatewayAssignment],
    ) -> dict[str, SiloGatewayAssignment]:
        mapping: dict[str, SiloGatewayAssignment] = {}
        for assignment in assignments:
            if assignment.role_slug in mapping:
                raise ValueError(f"Duplicate gateway assignment for role: {assignment.role_slug}")
            mapping[assignment.role_slug] = assignment
        return mapping

    async def _latest_runtime_operation(
        self,
        *,
        silo_id: UUID,
    ) -> SiloRuntimeHistoryEntryRead | None:
        if self._session is None:
            return None
        operations = await crud.list_by(
            self._session,
            SiloRuntimeOperation,
            silo_id=silo_id,
            order_by=(desc(col(SiloRuntimeOperation.created_at)),),
            limit=1,
        )
        if not operations:
            return None
        operation = operations[0]
        result_rows = await crud.list_by(
            self._session,
            SiloRuntimeOperationResult,
            operation_id=operation.id,
            order_by=(asc(col(SiloRuntimeOperationResult.created_at)),),
        )
        return SiloRuntimeHistoryEntryRead(
            mode="apply" if operation.mode == "apply" else "validate",
            created_at=operation.created_at.isoformat(),
            warnings=list(operation.warnings or []),
            results=[
                SiloRuntimeOperationRead(
                    role_slug=row.role_slug,
                    runtime_kind="gateway" if row.runtime_kind == "gateway" else "symphony",
                    gateway_name=row.gateway_name,
                    supports_picoclaw_bundle_apply=row.supports_picoclaw_bundle_apply,
                    validated=RuntimeBundleValidateResponseRead.model_validate(row.validated)
                    if row.validated
                    else None,
                    applied=RuntimeBundleApplyResponseRead.model_validate(row.applied)
                    if row.applied
                    else None,
                    warnings=list(row.warnings or []),
                )
                for row in result_rows
            ],
        )


def _slugify(value: str) -> str:
    normalized = _SLUG_SANITIZER_RE.sub("-", value.strip().lower()).strip("-")
    return normalized or "silo"
