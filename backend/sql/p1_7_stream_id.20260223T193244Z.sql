-- P1-7: stream_id dimension for events
-- NOTE: Run on Postgres with sufficient privileges.

-- 1) Add column (safe)
ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS stream_id text;

-- 2) Default + backfill + NOT NULL
ALTER TABLE public.events
  ALTER COLUMN stream_id SET DEFAULT 'prod';

UPDATE public.events
SET stream_id='prod'
WHERE stream_id IS NULL;

ALTER TABLE public.events
  ALTER COLUMN stream_id SET NOT NULL;

-- 3) Index used by scoped readers (health, /events, pipeline builders)
CREATE INDEX IF NOT EXISTS ix_events_scope_stream_ts
  ON public.events (org_id, home_id, subject_id, stream_id, "timestamp");

-- 4) Stream-aware uniqueness (allows same event_id in test + prod)
-- Drop legacy uniqueness on (org_id,home_id,event_id) if present
ALTER TABLE public.events DROP CONSTRAINT IF EXISTS events_event_id_unique;
DROP INDEX IF EXISTS public.ux_events_scope_event_id;
DROP INDEX IF EXISTS public.events_event_id_unique;

CREATE UNIQUE INDEX IF NOT EXISTS ux_events_scope_stream_event_id
  ON public.events (org_id, home_id, stream_id, event_id);
