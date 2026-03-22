"""Provision-plan rendering from silo desired state to PicoClaw bundle contracts."""

from __future__ import annotations

from uuid import UUID

from app.db import crud
from app.models.silo_roles import SiloRole
from app.models.silos import Silo
from app.schemas.silos import (
    RuntimeBundleFileRead,
    RuntimeBundleSecretBindingRead,
    RuntimeBundleValidateRequestRead,
    SiloCreate,
    SiloPreviewRead,
    SiloProvisionPlanRead,
    SiloProvisionPlanTargetRead,
    SiloRoleDesiredState,
    SiloSecretBinding,
)
from app.services.silos.service import SiloService


class ProvisionPlanService:
    """Render PicoClaw runtime bundle previews from silo create inputs."""

    def __init__(self, silo_service: SiloService | None = None) -> None:
        self._silo_service = silo_service or SiloService()

    def build_plan(self, payload: SiloCreate) -> SiloProvisionPlanRead:
        """Build a provision plan from silo desired state."""
        preview = self._silo_service.build_preview(payload)
        return self.build_plan_from_preview(preview)

    async def build_plan_for_silo(
        self,
        *,
        organization_id: UUID,
        slug: str,
    ) -> SiloProvisionPlanRead:
        """Build a provision plan from one persisted silo."""
        session = self._silo_service._session
        if session is None:
            raise RuntimeError(
                "ProvisionPlanService.build_plan_for_silo requires a database session"
            )

        silo = await crud.get_one_by(
            session,
            Silo,
            organization_id=organization_id,
            slug=slug,
        )
        if silo is None:
            raise ValueError(f"Silo not found: {slug}")

        preview = SiloPreviewRead.model_validate(silo.desired_state or {})
        role_rows = await crud.list_by(session, SiloRole, silo_id=silo.id)
        preview.roles = [
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
                secret_bindings=[
                    SiloSecretBinding.model_validate(binding)
                    for binding in (role.secret_bindings or [])
                ],
            )
            for role in role_rows
        ]

        return self.build_plan_from_preview(preview)

    def build_plan_from_preview(self, preview: SiloPreviewRead) -> SiloProvisionPlanRead:
        """Build a provision plan from a resolved preview."""
        targets: list[SiloProvisionPlanTargetRead] = []
        warnings = list(preview.warnings)

        for role in preview.roles:
            if role.runtime_kind == "gateway":
                targets.append(self._build_gateway_target(preview, role))
                continue

            target_warnings = [
                "Symphony runtime is not yet rendered into PicoClaw bundle apply payloads.",
            ]
            warnings.extend(target_warnings)
            targets.append(
                SiloProvisionPlanTargetRead(
                    role_slug=role.slug,
                    runtime_kind=role.runtime_kind,
                    gateway_name=role.gateway_name,
                    workspace_root=role.workspace_root,
                    supports_picoclaw_bundle_apply=False,
                    warnings=target_warnings,
                ),
            )
        return SiloProvisionPlanRead(preview=preview, targets=targets, warnings=warnings)

    def _build_gateway_target(
        self,
        preview: SiloPreviewRead,
        role: SiloRoleDesiredState,
    ) -> SiloProvisionPlanTargetRead:
        workspace_root = role.workspace_root or "~/.openclaw"
        workspace_path = f"{workspace_root.rstrip('/')}/workspace"

        config_patch: dict[str, object] = {
            "agents": {
                "defaults": {
                    "workspace": workspace_path,
                    "model_name": role.default_model,
                    "model_fallbacks": [role.fallback_model] if role.fallback_model else [],
                },
            },
            "channels": {
                "discord": {
                    "enabled": True,
                    "token": {"$secret": f"{role.slug}_discord_bot_token"},
                },
            },
        }

        files = [
            RuntimeBundleFileRead(
                root="workspace",
                path="AGENTS.md",
                content=self._render_agents_md(preview, role),
            ),
            RuntimeBundleFileRead(
                root="workspace",
                path="SOUL.md",
                content=self._render_soul_md(preview, role),
            ),
            RuntimeBundleFileRead(
                root="workspace",
                path="TEAM.md",
                content=self._render_team_md(preview),
            ),
        ]

        secret_bindings = [
            RuntimeBundleSecretBindingRead(
                name=binding.name,
                env_var=binding.env_var,
                required=binding.required,
            )
            for binding in [*preview.shared_secret_bindings, *role.secret_bindings]
        ]

        return SiloProvisionPlanTargetRead(
            role_slug=role.slug,
            runtime_kind=role.runtime_kind,
            gateway_name=role.gateway_name,
            workspace_root=workspace_root,
            supports_picoclaw_bundle_apply=True,
            bundle=RuntimeBundleValidateRequestRead(
                config_patch=config_patch,
                files=files,
                secret_bindings=secret_bindings,
            ),
        )

    def _render_agents_md(self, preview: SiloPreviewRead, role: SiloRoleDesiredState) -> str:
        lines = [
            "# AGENTS.md",
            "",
            f"Silo: {preview.name}",
            f"Blueprint: {preview.blueprint_slug}@{preview.blueprint_version}",
            f"Role: {role.display_name} ({role.role_type})",
            "",
            "Read SOUL.md and TEAM.md before starting work.",
        ]
        if role.channel_name:
            lines.append(f"Primary channel: {role.channel_name}")
        return "\n".join(lines) + "\n"

    def _render_soul_md(self, preview: SiloPreviewRead, role: SiloRoleDesiredState) -> str:
        return (
            "# SOUL.md\n\n"
            f"You are {role.display_name}, the {role.role_type} role in silo {preview.name}.\n"
            "Work directly, keep evidence real, and escalate blockers early.\n"
        )

    def _render_team_md(self, preview: SiloPreviewRead) -> str:
        role_lines = [f"- {role.display_name}: {role.role_type}" for role in preview.roles]
        return (
            "# TEAM.md\n\n"
            f"Silo: {preview.name}\n"
            f"Blueprint: {preview.blueprint_slug}@{preview.blueprint_version}\n\n"
            "Roles:\n" + "\n".join(role_lines) + "\n"
        )
