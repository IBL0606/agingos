BEGIN;

-- 1) Monitor/rule mode (OFF/TEST/ON) per target
CREATE TABLE IF NOT EXISTS monitor_modes (
  monitor_key   TEXT NOT NULL,
  room_id       TEXT NULL,
  mode          TEXT NOT NULL CHECK (mode IN ('OFF','TEST','ON')),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (monitor_key, room_id)
);

CREATE INDEX IF NOT EXISTS ix_monitor_modes_mode ON monitor_modes (mode);

-- 2) Extend proposals with type/target/evidence + dedupe, without touching lifecycle state machine
ALTER TABLE proposals
  ADD COLUMN IF NOT EXISTS proposal_type   TEXT NOT NULL DEFAULT 'UNSPECIFIED',
  ADD COLUMN IF NOT EXISTS dedupe_key      TEXT NOT NULL DEFAULT 'UNSPECIFIED',
  ADD COLUMN IF NOT EXISTS target          JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS evidence        JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS evidence_hash   TEXT NULL,
  ADD COLUMN IF NOT EXISTS evidence_refreshed_at TIMESTAMPTZ NULL;

-- 3) Uniqueness/dedupe for "live" proposals (NEW/TESTING/ACTIVE)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'public'
      AND indexname = 'ux_proposals_live_dedupe_key'
  ) THEN
    EXECUTE '
      CREATE UNIQUE INDEX ux_proposals_live_dedupe_key
      ON proposals (dedupe_key)
      WHERE state IN (''NEW'',''TESTING'',''ACTIVE'');
    ';
  END IF;
END$$;

-- 4) Query helpers for miner / ops
CREATE INDEX IF NOT EXISTS ix_proposals_type_state ON proposals (proposal_type, state);
CREATE INDEX IF NOT EXISTS ix_proposals_state ON proposals (state);
CREATE INDEX IF NOT EXISTS ix_proposals_evidence_refreshed_at ON proposals (evidence_refreshed_at);

COMMIT;
