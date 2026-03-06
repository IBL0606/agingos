"""reconcile runtime schema for weekly report endpoints

Revision ID: 9c5f1a2b7e44
Revises: a8f9c2d1e4b7
Create Date: 2026-03-06
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "9c5f1a2b7e44"
down_revision = "a8f9c2d1e4b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # proposals: required by /proposals scope filter in backend/main.py
    op.execute("ALTER TABLE proposals ADD COLUMN IF NOT EXISTS home_id TEXT")
    op.execute("UPDATE proposals SET home_id = 'default' WHERE home_id IS NULL")
    op.execute("ALTER TABLE proposals ALTER COLUMN home_id SET DEFAULT 'default'")
    op.execute("ALTER TABLE proposals ALTER COLUMN home_id SET NOT NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_proposals_scope_updated "
        "ON proposals(org_id, home_id, subject_id, updated_at DESC)"
    )

    # anomaly_episodes: required by ORM/query used by /anomalies
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS start_bucket TIMESTAMPTZ")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS last_bucket TIMESTAMPTZ")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS peak_bucket TIMESTAMPTZ")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS peak_score DOUBLE PRECISION")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS last_score DOUBLE PRECISION")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS last_level TEXT")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS green_streak INTEGER")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS bucket_count INTEGER")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS closed_reason TEXT")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS reasons_peak JSONB")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS reasons_last JSONB")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS org_id TEXT")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS home_id TEXT")
    op.execute("ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS subject_id TEXT")

    op.execute("UPDATE anomaly_episodes SET green_streak = 0 WHERE green_streak IS NULL")
    op.execute("UPDATE anomaly_episodes SET bucket_count = 0 WHERE bucket_count IS NULL")
    op.execute("UPDATE anomaly_episodes SET org_id = 'default' WHERE org_id IS NULL")
    op.execute("UPDATE anomaly_episodes SET home_id = 'default' WHERE home_id IS NULL")
    op.execute("UPDATE anomaly_episodes SET subject_id = 'default' WHERE subject_id IS NULL")

    op.execute("ALTER TABLE anomaly_episodes ALTER COLUMN green_streak SET DEFAULT 0")
    op.execute("ALTER TABLE anomaly_episodes ALTER COLUMN bucket_count SET DEFAULT 0")
    op.execute("ALTER TABLE anomaly_episodes ALTER COLUMN org_id SET DEFAULT 'default'")
    op.execute("ALTER TABLE anomaly_episodes ALTER COLUMN home_id SET DEFAULT 'default'")
    op.execute("ALTER TABLE anomaly_episodes ALTER COLUMN subject_id SET DEFAULT 'default'")

    op.execute("ALTER TABLE anomaly_episodes ALTER COLUMN green_streak SET NOT NULL")
    op.execute("ALTER TABLE anomaly_episodes ALTER COLUMN bucket_count SET NOT NULL")
    op.execute("ALTER TABLE anomaly_episodes ALTER COLUMN org_id SET NOT NULL")
    op.execute("ALTER TABLE anomaly_episodes ALTER COLUMN home_id SET NOT NULL")
    op.execute("ALTER TABLE anomaly_episodes ALTER COLUMN subject_id SET NOT NULL")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_anomaly_episodes_scope_start "
        "ON anomaly_episodes(org_id, home_id, subject_id, start_ts DESC)"
    )


def downgrade() -> None:
    # Keep downgrade safe/non-destructive for existing environments.
    op.execute("DROP INDEX IF EXISTS ix_anomaly_episodes_scope_start")
    op.execute("DROP INDEX IF EXISTS ix_proposals_scope_updated")
