"""Default silo blueprint builders used by the Mission Control MVP."""

from __future__ import annotations

from app.schemas.silos import (
    SiloBlueprintRead,
    SiloProvisionTarget,
    SiloRoleBlueprint,
    SiloSecretBinding,
)

DEFAULT_PRIMARY_MODEL = "anthropic/claude-sonnet-4-6"
DEFAULT_FALLBACK_MODEL = "openai-codex/gpt-5.3-codex"


def _shared_secret_bindings() -> list[SiloSecretBinding]:
    return [
        SiloSecretBinding(
            name="anthropic_api_key",
            vault_path="secret/shared/anthropic",
            vault_key="ANTHROPIC_API_KEY",
            env_var="ANTHROPIC_API_KEY",
        ),
        SiloSecretBinding(
            name="linear_api_key",
            vault_path="secret/shared/linear",
            vault_key="LINEAR_API_KEY",
            env_var="LINEAR_API_KEY",
        ),
    ]


def _role_secret_bindings(role_slug: str) -> list[SiloSecretBinding]:
    bindings = [
        SiloSecretBinding(
            name=f"{role_slug}_discord_bot_token",
            vault_path=f"secret/agents/{role_slug}/discord",
            vault_key="DISCORD_BOT_TOKEN",
            env_var="DISCORD_BOT_TOKEN",
        ),
        SiloSecretBinding(
            name=f"{role_slug}_gateway_token",
            vault_path=f"secret/agents/{role_slug}/discord",
            vault_key="GATEWAY_TOKEN",
            env_var="GATEWAY_TOKEN",
        ),
    ]

    if role_slug == "bunny":
        bindings.extend(
            [
                SiloSecretBinding(
                    name="bunny_figma_pat",
                    vault_path="secret/agents/bunny/figma",
                    vault_key="FIGMA_PAT",
                    env_var="FIGMA_PAT",
                ),
                SiloSecretBinding(
                    name="bunny_notion_api_key",
                    vault_path="secret/agents/bunny/notion",
                    vault_key="NOTION_API_KEY",
                    env_var="NOTION_API_KEY",
                ),
            ],
        )

    return bindings


def build_default_four_agent_blueprint() -> SiloBlueprintRead:
    """Return the reference 4-agent blueprint used for MVP silo creation."""
    roles = [
        SiloRoleBlueprint(
            slug="fox",
            display_name="Fox",
            role_type="pm",
            description="Project manager and coordination lead.",
            host_kind="ec2",
            runtime_kind="gateway",
            default_model=DEFAULT_PRIMARY_MODEL,
            fallback_model=DEFAULT_FALLBACK_MODEL,
            channel_name="fox-tasks",
            secret_bindings=_role_secret_bindings("fox"),
        ),
        SiloRoleBlueprint(
            slug="bunny",
            display_name="Bunny",
            role_type="designer",
            description="Design lead with Figma and documentation workflows.",
            host_kind="mac",
            runtime_kind="gateway",
            default_model=DEFAULT_PRIMARY_MODEL,
            fallback_model=DEFAULT_FALLBACK_MODEL,
            channel_name="bunny-tasks",
            secret_bindings=_role_secret_bindings("bunny"),
        ),
        SiloRoleBlueprint(
            slug="owl",
            display_name="Owl",
            role_type="tech_lead",
            description="Technical lead for architecture and review.",
            host_kind="pi",
            runtime_kind="gateway",
            default_model=DEFAULT_PRIMARY_MODEL,
            fallback_model=DEFAULT_FALLBACK_MODEL,
            channel_name="owl-tasks",
            secret_bindings=_role_secret_bindings("owl"),
        ),
        SiloRoleBlueprint(
            slug="otter",
            display_name="Otter",
            role_type="engineer",
            description="Implementation engineer and Symphony host.",
            host_kind="ec2",
            runtime_kind="gateway",
            default_model=DEFAULT_PRIMARY_MODEL,
            fallback_model=DEFAULT_FALLBACK_MODEL,
            channel_name="otter-tasks",
            secret_bindings=_role_secret_bindings("otter"),
        ),
        SiloRoleBlueprint(
            slug="symphony",
            display_name="Symphony",
            role_type="orchestrator",
            description="Optional coding orchestration worker.",
            host_kind="ec2",
            runtime_kind="symphony",
            default_model="claude-cli/claude",
            fallback_model="codex-cli/codex",
            secret_bindings=[],
        ),
    ]

    provision_targets = [
        SiloProvisionTarget(
            role_slug="fox",
            gateway_name="fox-gateway",
            workspace_root="~/.openclaw",
            runtime_kind="gateway",
        ),
        SiloProvisionTarget(
            role_slug="bunny",
            gateway_name="bunny-gateway",
            workspace_root="~/.openclaw",
            runtime_kind="gateway",
        ),
        SiloProvisionTarget(
            role_slug="owl",
            gateway_name="owl-gateway",
            workspace_root="~/.openclaw",
            runtime_kind="gateway",
        ),
        SiloProvisionTarget(
            role_slug="otter",
            gateway_name="otter-gateway",
            workspace_root="~/.openclaw",
            runtime_kind="gateway",
        ),
        SiloProvisionTarget(
            role_slug="symphony",
            gateway_name="otter-gateway",
            workspace_root="~/symphony",
            runtime_kind="symphony",
        ),
    ]

    return SiloBlueprintRead(
        slug="default-four-agent",
        version="0.1.0",
        display_name="Default Four-Agent Silo",
        description="Reference blueprint based on the Fox/Bunny/Owl/Otter operating model.",
        roles=roles,
        shared_secret_bindings=_shared_secret_bindings(),
        provision_targets=provision_targets,
        supports_symphony=True,
        supports_telemetry=True,
    )
