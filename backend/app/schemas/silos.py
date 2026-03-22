"""Silo and blueprint contracts for control-plane provisioning flows."""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator
from sqlmodel import Field, SQLModel


class SiloSecretBinding(SQLModel):
    """Logical secret reference used by renderers and runtime apply flows."""

    name: str
    vault_path: str
    vault_key: str
    env_var: str
    required: bool = True

    @field_validator("name", "vault_path", "vault_key", "env_var", mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> object:
        """Trim required text fields and reject blank strings."""
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                raise ValueError("value must not be blank")
            return trimmed
        return value


class SiloProvisionTarget(SQLModel):
    """Runtime target describing where a role should be provisioned."""

    role_slug: str
    gateway_name: str
    workspace_root: str
    runtime_kind: Literal["gateway", "symphony", "collector"] = "gateway"

    @field_validator("role_slug", "gateway_name", "workspace_root", mode="before")
    @classmethod
    def normalize_target_text(cls, value: object) -> object:
        """Trim target text values."""
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                raise ValueError("value must not be blank")
            return trimmed
        return value


class SiloRoleBlueprint(SQLModel):
    """Desired role definition within a silo blueprint."""

    slug: str
    display_name: str
    role_type: Literal["pm", "designer", "tech_lead", "engineer", "orchestrator"]
    description: str = ""
    host_kind: Literal["mac", "linux", "pi", "ec2", "generic"] = "generic"
    runtime_kind: Literal["gateway", "symphony"] = "gateway"
    default_model: str | None = None
    fallback_model: str | None = None
    channel_name: str | None = None
    secret_bindings: list[SiloSecretBinding] = Field(default_factory=list)

    @field_validator("slug", "display_name", mode="before")
    @classmethod
    def normalize_role_text(cls, value: object) -> object:
        """Trim text role identifiers."""
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                raise ValueError("value must not be blank")
            return trimmed
        return value


class SiloBlueprintRead(SQLModel):
    """Published blueprint description returned by blueprint services."""

    slug: str
    version: str
    display_name: str
    description: str = ""
    roles: list[SiloRoleBlueprint] = Field(default_factory=list)
    shared_secret_bindings: list[SiloSecretBinding] = Field(default_factory=list)
    provision_targets: list[SiloProvisionTarget] = Field(default_factory=list)
    supports_symphony: bool = False
    supports_telemetry: bool = False


class SiloRead(SQLModel):
    """Read model returned for silo overview pages."""

    id: str | None = None
    slug: str
    name: str
    blueprint_slug: str
    blueprint_version: str
    status: Literal["draft", "provisioning", "active", "paused", "archived"] = "draft"
    enable_symphony: bool = False
    enable_telemetry: bool = False
    role_count: int = 0
    active_run_count: int = 0
    blocked_run_count: int = 0
    failed_run_count: int = 0
    last_activity_at: str | None = None


class SiloRoleDesiredState(SQLModel):
    """Resolved role state returned by silo preview flows."""

    slug: str
    display_name: str
    role_type: Literal["pm", "designer", "tech_lead", "engineer", "orchestrator"]
    runtime_kind: Literal["gateway", "symphony"]
    host_kind: Literal["mac", "linux", "pi", "ec2", "generic"]
    default_model: str | None = None
    fallback_model: str | None = None
    channel_name: str | None = None
    gateway_id: str | None = None
    gateway_name: str | None = None
    workspace_root: str | None = None
    secret_bindings: list[SiloSecretBinding] = Field(default_factory=list)


class SiloGatewayAssignment(SQLModel):
    """Explicit runtime gateway assignment override for one role."""

    role_slug: str
    gateway_id: str | None = None
    workspace_root: str | None = None

    @field_validator("role_slug", mode="before")
    @classmethod
    def normalize_role_slug(cls, value: object) -> object:
        """Trim role slug values."""
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                raise ValueError("value must not be blank")
            return trimmed
        return value


class SiloCreate(SQLModel):
    """MVP create payload for a new silo instance."""

    name: str
    blueprint_slug: str
    spawn_request_id: str | None = None
    blueprint_version: str | None = None
    owner_display_name: str | None = None
    enable_symphony: bool = False
    enable_telemetry: bool = False
    gateway_assignments: list[SiloGatewayAssignment] = Field(default_factory=list)

    @field_validator("name", "blueprint_slug", mode="before")
    @classmethod
    def normalize_silo_text(cls, value: object) -> object:
        """Trim required create text fields."""
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                raise ValueError("value must not be blank")
            return trimmed
        return value


class SiloUpdate(SQLModel):
    """Patch payload for persisted silo assignment and toggle updates."""

    enable_symphony: bool | None = None
    enable_telemetry: bool | None = None
    gateway_assignments: list[SiloGatewayAssignment] = Field(default_factory=list)


class SiloPreviewRead(SQLModel):
    """Desired-state preview returned before silo persistence/provisioning."""

    slug: str
    name: str
    blueprint_slug: str
    blueprint_version: str
    enable_symphony: bool = False
    enable_telemetry: bool = False
    roles: list[SiloRoleDesiredState] = Field(default_factory=list)
    shared_secret_bindings: list[SiloSecretBinding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RuntimeBundleSecretBindingRead(SQLModel):
    """Picoclaw runtime bundle secret binding contract."""

    name: str
    env_var: str
    required: bool = True


class RuntimeBundleFileRead(SQLModel):
    """Picoclaw runtime bundle file contract."""

    root: Literal["workspace", "config_dir"]
    path: str
    content: str
    perm: str = "0644"


class RuntimeBundleValidateRequestRead(SQLModel):
    """Picoclaw runtime bundle validate/apply request contract."""

    config_patch: dict[str, object] | None = None
    launcher_config: dict[str, object] | None = None
    files: list[RuntimeBundleFileRead] = Field(default_factory=list)
    secret_bindings: list[RuntimeBundleSecretBindingRead] = Field(default_factory=list)


class RuntimeBundleWritePlanRead(SQLModel):
    """Picoclaw runtime bundle write-plan contract."""

    root: Literal["workspace", "config_dir"]
    path: str
    target_path: str
    perm: str = "0644"
    bytes: int


class RuntimeBundleSecretUseRead(SQLModel):
    """Resolved secret usage returned by picoclaw bundle operations."""

    name: str
    env_var: str
    required: bool = True
    used_by: list[str] = Field(default_factory=list)


class RuntimeBundleValidateResponseRead(SQLModel):
    """Picoclaw runtime bundle validate response contract."""

    valid: bool
    restart_required: bool = False
    warnings: list[str] = Field(default_factory=list)
    writes: list[RuntimeBundleWritePlanRead] = Field(default_factory=list)
    resolved_secrets: list[RuntimeBundleSecretUseRead] = Field(default_factory=list)


class RuntimeBundleApplyResponseRead(SQLModel):
    """Picoclaw runtime bundle apply response contract."""

    applied: bool
    restart_required: bool = False
    warnings: list[str] = Field(default_factory=list)
    writes: list[RuntimeBundleWritePlanRead] = Field(default_factory=list)
    resolved_secrets: list[RuntimeBundleSecretUseRead] = Field(default_factory=list)


class SiloProvisionPlanTargetRead(SQLModel):
    """One provision target derived from a silo preview."""

    role_slug: str
    runtime_kind: Literal["gateway", "symphony"]
    gateway_name: str | None = None
    workspace_root: str | None = None
    supports_picoclaw_bundle_apply: bool = False
    bundle: RuntimeBundleValidateRequestRead | None = None
    warnings: list[str] = Field(default_factory=list)


class SiloProvisionPlanRead(SQLModel):
    """Provision plan preview derived from a desired silo state."""

    preview: SiloPreviewRead
    targets: list[SiloProvisionPlanTargetRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SiloRuntimeOperationRead(SQLModel):
    """One target result from validating or applying a persisted silo plan."""

    role_slug: str
    runtime_kind: Literal["gateway", "symphony"]
    gateway_name: str | None = None
    supports_picoclaw_bundle_apply: bool = False
    validated: RuntimeBundleValidateResponseRead | None = None
    applied: RuntimeBundleApplyResponseRead | None = None
    warnings: list[str] = Field(default_factory=list)


class SiloRuntimeOperationResponseRead(SQLModel):
    """Aggregate runtime operation result for one persisted silo."""

    silo: SiloRead
    mode: Literal["validate", "apply"]
    results: list[SiloRuntimeOperationRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SiloRuntimeHistoryEntryRead(SQLModel):
    """Latest persisted runtime operation snapshot for one silo."""

    mode: Literal["validate", "apply"]
    created_at: str
    results: list[SiloRuntimeOperationRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SiloWorkloadRunRead(SQLModel):
    """Recent execution run summary scoped to one silo."""

    id: str
    board_id: str
    task_id: str
    task_title: str
    task_status: str | None = None
    task_priority: str | None = None
    role_slug: str
    status: Literal[
        "queued",
        "dispatching",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "blocked",
    ]
    summary: str | None = None
    completion_kind: str | None = None
    failure_reason: str | None = None
    block_reason: str | None = None
    cancel_reason: str | None = None
    stall_reason: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None


class SiloWorkloadSummaryRead(SQLModel):
    """Operator-facing workload summary for one silo."""

    active_run_count: int = 0
    queued_run_count: int = 0
    running_run_count: int = 0
    blocked_run_count: int = 0
    failed_run_count: int = 0
    recent_runs: list[SiloWorkloadRunRead] = Field(default_factory=list)
    last_activity_at: str | None = None


class SiloDetailRead(SQLModel):
    """Detailed silo view for operator-facing Silo Detail pages."""

    source_request_id: str | None = None
    source_request_slug: str | None = None
    source_request_status: str | None = None
    source_request_display_name: str | None = None
    silo: SiloRead
    desired_state: SiloPreviewRead
    roles: list[SiloRoleDesiredState] = Field(default_factory=list)
    provision_plan: SiloProvisionPlanRead | None = None
    latest_runtime_operation: SiloRuntimeHistoryEntryRead | None = None
    workload_summary: SiloWorkloadSummaryRead | None = None
