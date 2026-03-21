from app.schemas.silos import SiloCreate, SiloSecretBinding
from app.services.silos import build_default_four_agent_blueprint


def test_default_four_agent_blueprint_has_expected_roles() -> None:
    blueprint = build_default_four_agent_blueprint()

    assert blueprint.slug == "default-four-agent"
    assert blueprint.supports_symphony is True
    assert blueprint.supports_telemetry is True

    role_slugs = [role.slug for role in blueprint.roles]
    assert role_slugs == ["fox", "bunny", "owl", "otter", "symphony"]


def test_default_four_agent_blueprint_uses_secret_bindings_not_secret_values() -> None:
    blueprint = build_default_four_agent_blueprint()

    bunny = next(role for role in blueprint.roles if role.slug == "bunny")
    figma_binding = next(
        binding for binding in bunny.secret_bindings if binding.name == "bunny_figma_pat"
    )

    assert figma_binding.vault_path == "secret/agents/bunny/figma"
    assert figma_binding.vault_key == "FIGMA_PAT"
    assert figma_binding.env_var == "FIGMA_PAT"


def test_secret_binding_rejects_blank_values() -> None:
    try:
        SiloSecretBinding(
            name="   ",
            vault_path="secret/shared/anthropic",
            vault_key="ANTHROPIC_API_KEY",
            env_var="ANTHROPIC_API_KEY",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("blank secret binding name should raise ValueError")


def test_silo_create_normalizes_required_fields() -> None:
    payload = SiloCreate(name=" Demo ", blueprint_slug=" default-four-agent ")

    assert payload.name == "Demo"
    assert payload.blueprint_slug == "default-four-agent"
