   AND s.subject_id = r.out_subject
  WHERE s.model_end = end_day;
END $$;;

UPDATE alembic_version SET version_num='a8f9c2d1e4b7' WHERE alembic_version.version_num = '169d4a5837e0';

-- Running upgrade a8f9c2d1e4b7 -> 9c5f1a2b7e44

ALTER TABLE proposals ADD COLUMN IF NOT EXISTS home_id TEXT;

UPDATE proposals SET home_id = 'default' WHERE home_id IS NULL;

ALTER TABLE proposals ALTER COLUMN home_id SET DEFAULT 'default';

ALTER TABLE proposals ALTER COLUMN home_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_proposals_scope_updated ON proposals(org_id, home_id, subject_id, updated_at DESC);

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS start_bucket TIMESTAMPTZ;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS last_bucket TIMESTAMPTZ;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS peak_bucket TIMESTAMPTZ;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS peak_score DOUBLE PRECISION;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS last_score DOUBLE PRECISION;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS last_level TEXT;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS green_streak INTEGER;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS bucket_count INTEGER;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS closed_reason TEXT;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS reasons_peak JSONB;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS reasons_last JSONB;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS org_id TEXT;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS home_id TEXT;

ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS subject_id TEXT;

UPDATE anomaly_episodes SET green_streak = 0 WHERE green_streak IS NULL;

UPDATE anomaly_episodes SET bucket_count = 0 WHERE bucket_count IS NULL;

UPDATE anomaly_episodes SET org_id = 'default' WHERE org_id IS NULL;

UPDATE anomaly_episodes SET home_id = 'default' WHERE home_id IS NULL;

UPDATE anomaly_episodes SET subject_id = 'default' WHERE subject_id IS NULL;

ALTER TABLE anomaly_episodes ALTER COLUMN green_streak SET DEFAULT 0;

ALTER TABLE anomaly_episodes ALTER COLUMN bucket_count SET DEFAULT 0;

ALTER TABLE anomaly_episodes ALTER COLUMN org_id SET DEFAULT 'default';

ALTER TABLE anomaly_episodes ALTER COLUMN home_id SET DEFAULT 'default';

ALTER TABLE anomaly_episodes ALTER COLUMN subject_id SET DEFAULT 'default';

ALTER TABLE anomaly_episodes ALTER COLUMN green_streak SET NOT NULL;

ALTER TABLE anomaly_episodes ALTER COLUMN bucket_count SET NOT NULL;

ALTER TABLE anomaly_episodes ALTER COLUMN org_id SET NOT NULL;

ALTER TABLE anomaly_episodes ALTER COLUMN home_id SET NOT NULL;

ALTER TABLE anomaly_episodes ALTER COLUMN subject_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_anomaly_episodes_scope_start ON anomaly_episodes(org_id, home_id, subject_id, start_ts DESC);

UPDATE alembic_version SET version_num='9c5f1a2b7e44' WHERE alembic_version.version_num = 'a8f9c2d1e4b7';

COMMIT;

