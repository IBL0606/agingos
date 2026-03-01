"""fresh install schema: scoped events + api_key_scopes + baseline tables

Revision ID: 16675adff372
Revises: 3f36f67c80c7
Create Date: 2026-03-01 18:22:44.261829

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "16675adff372"
down_revision: Union[str, None] = "3f36f67c80c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Events: add scoped columns + room_id (match MiniPC schema)
    op.add_column("events", sa.Column("org_id", sa.Text(), nullable=False, server_default=sa.text("'default'")))
    op.add_column("events", sa.Column("home_id", sa.Text(), nullable=False, server_default=sa.text("'default'")))
    op.add_column("events", sa.Column("subject_id", sa.Text(), nullable=False, server_default=sa.text("'default'")))
    op.add_column("events", sa.Column("stream_id", sa.Text(), nullable=False, server_default=sa.text("'prod'")))
    op.add_column("events", sa.Column("room_id", sa.Text(), nullable=True))

    op.create_index("ix_events_scope_ts", "events", ["org_id", "home_id", "subject_id", "timestamp"], unique=False)
    op.create_index("ix_events_scope_stream_ts", "events", ["org_id", "home_id", "subject_id", "stream_id", "timestamp"], unique=False)
    op.create_index("ix_events_scope_room_ts", "events", ["org_id", "home_id", "subject_id", "room_id", "timestamp"], unique=False)
    op.create_unique_constraint("ux_events_scope_stream_event_id", "events", ["org_id", "home_id", "stream_id", "event_id"])

    # remove server defaults (keep NOT NULL)
    op.alter_column("events", "org_id", server_default=None)
    op.alter_column("events", "home_id", server_default=None)
    op.alter_column("events", "subject_id", server_default=None)
    op.alter_column("events", "stream_id", server_default=None)

    # 2) API key scopes table
    op.create_table(
        "api_key_scopes",
        sa.Column("org_id", sa.Text(), nullable=False),
        sa.Column("home_id", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("api_key_hash", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_unique_constraint("api_key_scopes_uq", "api_key_scopes", ["api_key_hash"])

    # 3) Baseline tables (as seen on MiniPC)
    op.create_table(
        "baseline_bucket_dim",
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bucket_end", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("bucket_start"),
    )

    op.create_table(
        "baseline_model_status",
        sa.Column("org_id", sa.Text(), nullable=False),
        sa.Column("home_id", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("model_start", sa.Date(), nullable=False),
        sa.Column("model_end", sa.Date(), nullable=False),
        sa.Column("baseline_ready", sa.Boolean(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("days_in_window", sa.Integer(), nullable=False),
        sa.Column("days_with_data", sa.Integer(), nullable=False),
        sa.Column("room_bucket_rows", sa.Integer(), nullable=False),
        sa.Column("room_bucket_supported", sa.Boolean(), nullable=False),
        sa.Column("transition_rows", sa.Integer(), nullable=False),
        sa.Column("transition_supported", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("org_id", "home_id", "subject_id", "model_end"),
    )

    op.create_table(
        "baseline_room_bucket",
        sa.Column("org_id", sa.Text(), nullable=False),
        sa.Column("home_id", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("room_id", sa.Text(), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bucket_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("presence_n", sa.Integer(), nullable=False),
        sa.Column("motion_n", sa.Integer(), nullable=False),
        sa.Column("door_n", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("org_id", "home_id", "subject_id", "room_id", "bucket_start"),
    )

    op.create_table(
        "baseline_transition",
        sa.Column("org_id", sa.Text(), nullable=False),
        sa.Column("home_id", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("from_room_id", sa.Text(), nullable=False),
        sa.Column("to_room_id", sa.Text(), nullable=False),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("org_id", "home_id", "subject_id", "from_room_id", "to_room_id", "window_end"),
    )


def downgrade() -> None:
    op.drop_table("baseline_transition")
    op.drop_table("baseline_room_bucket")
    op.drop_table("baseline_model_status")
    op.drop_table("baseline_bucket_dim")

    op.drop_constraint("api_key_scopes_uq", "api_key_scopes", type_="unique")
    op.drop_table("api_key_scopes")

    op.drop_constraint("ux_events_scope_stream_event_id", "events", type_="unique")
    op.drop_index("ix_events_scope_room_ts", table_name="events")
    op.drop_index("ix_events_scope_stream_ts", table_name="events")
    op.drop_index("ix_events_scope_ts", table_name="events")
    op.drop_column("events", "room_id")
    op.drop_column("events", "stream_id")
    op.drop_column("events", "subject_id")
    op.drop_column("events", "home_id")
    op.drop_column("events", "org_id")
