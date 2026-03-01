"""add monitor_modes + scope columns for deviations

Revision ID: 3f36f67c80c7
Revises: 13e17df70380
Create Date: 2026-02-20

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3f36f67c80c7"
down_revision = "13e17df70380"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- deviations: add scope columns (non-null, default "default") ---
    op.add_column(
        "deviations",
        sa.Column(
            "org_id", sa.String(length=200), nullable=False, server_default="default"
        ),
    )
    op.add_column(
        "deviations",
        sa.Column(
            "home_id", sa.String(length=200), nullable=False, server_default="default"
        ),
    )
    op.add_column(
        "deviations",
        sa.Column(
            "subject_id",
            sa.String(length=200),
            nullable=False,
            server_default="default",
        ),
    )

    # Drop server_default to avoid hiding missing scope in future inserts
    op.alter_column("deviations", "org_id", server_default=None)
    op.alter_column("deviations", "home_id", server_default=None)
    op.alter_column("deviations", "subject_id", server_default=None)

    # Add index for scope filtering (scheduler queries)
    op.create_index(
        "ix_deviations_scope_status_last_seen",
        "deviations",
        ["org_id", "home_id", "subject_id", "status", "last_seen_at"],
        unique=False,
    )

    # Ensure only one ACTIVE deviation per rule+subject+scope (OPEN/ACK)
    op.create_index(
        "uq_deviations_active_rule_subject_scope",
        "deviations",
        ["rule_id", "subject_key", "org_id", "home_id", "subject_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN','ACK')"),
    )

    # --- monitor_modes: enable OFF/TEST/ON gating ---
    op.create_table(
        "monitor_modes",
        sa.Column("org_id", sa.String(length=200), nullable=False),
        sa.Column("home_id", sa.String(length=200), nullable=False),
        sa.Column("subject_id", sa.String(length=200), nullable=False),
        sa.Column("monitor_key", sa.String(length=200), nullable=False),
        sa.Column(
            "room_id",
            sa.String(length=200),
            nullable=False,
            server_default="__GLOBAL__",
        ),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="ON"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "org_id",
            "home_id",
            "subject_id",
            "monitor_key",
            "room_id",
            name="monitor_modes_pkey",
        ),
    )

    op.create_index(
        "ix_monitor_modes_lookup",
        "monitor_modes",
        ["monitor_key", "room_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_monitor_modes_lookup", table_name="monitor_modes")
    op.drop_table("monitor_modes")

    op.drop_index("uq_deviations_active_rule_subject_scope", table_name="deviations")
    op.drop_index("ix_deviations_scope_status_last_seen", table_name="deviations")

    op.drop_column("deviations", "subject_id")
    op.drop_column("deviations", "home_id")
    op.drop_column("deviations", "org_id")
