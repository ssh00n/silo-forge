"""add silo mvp tables

Revision ID: b1c2d3e4f5a
Revises: a9b1c2d3e4f7
Create Date: 2026-03-20 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a"
down_revision = "a9b1c2d3e4f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "silos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("blueprint_slug", sa.String(), nullable=False),
        sa.Column("blueprint_version", sa.String(), nullable=False),
        sa.Column("owner_display_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("enable_symphony", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable_telemetry", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("desired_state", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_silos_org_slug"),
    )
    op.create_index(op.f("ix_silos_organization_id"), "silos", ["organization_id"], unique=False)
    op.create_index(op.f("ix_silos_slug"), "silos", ["slug"], unique=False)
    op.create_index(op.f("ix_silos_blueprint_slug"), "silos", ["blueprint_slug"], unique=False)
    op.create_index(op.f("ix_silos_status"), "silos", ["status"], unique=False)

    op.create_table(
        "silo_roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("silo_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("role_type", sa.String(), nullable=False),
        sa.Column("runtime_kind", sa.String(), nullable=False),
        sa.Column("host_kind", sa.String(), nullable=False),
        sa.Column("default_model", sa.String(), nullable=True),
        sa.Column("fallback_model", sa.String(), nullable=True),
        sa.Column("channel_name", sa.String(), nullable=True),
        sa.Column("gateway_id", sa.Uuid(), nullable=True),
        sa.Column("gateway_name", sa.String(), nullable=True),
        sa.Column("workspace_root", sa.String(), nullable=True),
        sa.Column("secret_bindings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["gateway_id"], ["gateways.id"]),
        sa.ForeignKeyConstraint(["silo_id"], ["silos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("silo_id", "slug", name="uq_silo_roles_silo_slug"),
    )
    op.create_index(op.f("ix_silo_roles_silo_id"), "silo_roles", ["silo_id"], unique=False)
    op.create_index(op.f("ix_silo_roles_slug"), "silo_roles", ["slug"], unique=False)
    op.create_index(op.f("ix_silo_roles_role_type"), "silo_roles", ["role_type"], unique=False)
    op.create_index(
        op.f("ix_silo_roles_runtime_kind"),
        "silo_roles",
        ["runtime_kind"],
        unique=False,
    )
    op.create_index(op.f("ix_silo_roles_gateway_id"), "silo_roles", ["gateway_id"], unique=False)

    op.create_table(
        "silo_runtime_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("silo_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["silo_id"], ["silos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_silo_runtime_operations_silo_id"),
        "silo_runtime_operations",
        ["silo_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_runtime_operations_mode"),
        "silo_runtime_operations",
        ["mode"],
        unique=False,
    )

    op.create_table(
        "silo_runtime_operation_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("role_slug", sa.String(), nullable=False),
        sa.Column("runtime_kind", sa.String(), nullable=False),
        sa.Column("gateway_name", sa.String(), nullable=True),
        sa.Column(
            "supports_picoclaw_bundle_apply",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("validated", sa.JSON(), nullable=True),
        sa.Column("applied", sa.JSON(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["operation_id"], ["silo_runtime_operations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_silo_runtime_operation_results_operation_id"),
        "silo_runtime_operation_results",
        ["operation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_runtime_operation_results_role_slug"),
        "silo_runtime_operation_results",
        ["role_slug"],
        unique=False,
    )
    op.create_index(
        op.f("ix_silo_runtime_operation_results_runtime_kind"),
        "silo_runtime_operation_results",
        ["runtime_kind"],
        unique=False,
    )

    op.alter_column("silos", "enable_symphony", server_default=None)
    op.alter_column("silos", "enable_telemetry", server_default=None)
    op.alter_column(
        "silo_runtime_operation_results",
        "supports_picoclaw_bundle_apply",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_silo_runtime_operation_results_runtime_kind"),
        table_name="silo_runtime_operation_results",
    )
    op.drop_index(
        op.f("ix_silo_runtime_operation_results_role_slug"),
        table_name="silo_runtime_operation_results",
    )
    op.drop_index(
        op.f("ix_silo_runtime_operation_results_operation_id"),
        table_name="silo_runtime_operation_results",
    )
    op.drop_table("silo_runtime_operation_results")

    op.drop_index(
        op.f("ix_silo_runtime_operations_mode"),
        table_name="silo_runtime_operations",
    )
    op.drop_index(
        op.f("ix_silo_runtime_operations_silo_id"),
        table_name="silo_runtime_operations",
    )
    op.drop_table("silo_runtime_operations")

    op.drop_index(op.f("ix_silo_roles_gateway_id"), table_name="silo_roles")
    op.drop_index(op.f("ix_silo_roles_runtime_kind"), table_name="silo_roles")
    op.drop_index(op.f("ix_silo_roles_role_type"), table_name="silo_roles")
    op.drop_index(op.f("ix_silo_roles_slug"), table_name="silo_roles")
    op.drop_index(op.f("ix_silo_roles_silo_id"), table_name="silo_roles")
    op.drop_table("silo_roles")

    op.drop_index(op.f("ix_silos_status"), table_name="silos")
    op.drop_index(op.f("ix_silos_blueprint_slug"), table_name="silos")
    op.drop_index(op.f("ix_silos_slug"), table_name="silos")
    op.drop_index(op.f("ix_silos_organization_id"), table_name="silos")
    op.drop_table("silos")
