BEGIN;

CREATE TABLE IF NOT EXISTS public.notification_policy (
  org_id text NOT NULL,
  home_id text NOT NULL,
  subject_id text NOT NULL,
  mode text NOT NULL DEFAULT 'NORMAL'
    CHECK (mode IN ('NORMAL','QUIET','NIGHT')),
  quiet_start_local time NULL,
  quiet_end_local time NULL,
  tz text NOT NULL DEFAULT 'Europe/Oslo',
  override_until timestamptz NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by text NULL,
  PRIMARY KEY (org_id, home_id, subject_id)
);

COMMIT;
