-- P1-1: Multi-subject attribution + subject state (MVP, deterministic)
-- Safe/additive: no changes to ingest. Uses explicit mapping rules.

\set ON_ERROR_STOP on

-- 1) Attribution rules table
CREATE TABLE IF NOT EXISTS public.event_attribution_rules (
  rule_id      bigserial PRIMARY KEY,
  org_id       text NOT NULL,
  home_id      text NOT NULL,
  source_kind  text NOT NULL,    -- e.g. 'ha_entity_id', 'payload_src'
  source_key   text NOT NULL,    -- e.g. entity_id string or src token
  subject_id   text NOT NULL,
  active       boolean NOT NULL DEFAULT true,
  note         text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_event_attr_rules_active
ON public.event_attribution_rules (org_id, home_id, source_kind, source_key)
WHERE active = true;

CREATE INDEX IF NOT EXISTS ix_event_attr_rules_lookup
ON public.event_attribution_rules (org_id, home_id, source_kind, source_key);

-- 2) Attributed events view v2 (HA entity_id first, then payload.src fallback)
CREATE OR REPLACE VIEW public.events_attributed_v2 AS
SELECT
  e.id,
  e.event_id,
  e."timestamp",
  e.category,
  e.payload,
  e.org_id,
  e.home_id,
  e.subject_id AS ingested_subject_id,

  (e.payload::jsonb->>'entity_id') AS ha_entity_id,
  (e.payload::jsonb->>'src')       AS payload_src,

  COALESCE(r_ha.subject_id, r_src.subject_id) AS attributed_subject_id,
  COALESCE(r_ha.rule_id,   r_src.rule_id)     AS attribution_rule_id,
  CASE
    WHEN r_ha.rule_id IS NOT NULL THEN 'ha_entity_id'
    WHEN r_src.rule_id IS NOT NULL THEN 'payload_src'
    ELSE NULL
  END AS attribution_kind

FROM public.events e
LEFT JOIN public.event_attribution_rules r_ha
  ON r_ha.active = true
 AND r_ha.org_id = e.org_id
 AND r_ha.home_id = e.home_id
 AND r_ha.source_kind = 'ha_entity_id'
 AND r_ha.source_key = (e.payload::jsonb->>'entity_id')

LEFT JOIN public.event_attribution_rules r_src
  ON r_src.active = true
 AND r_src.org_id = e.org_id
 AND r_src.home_id = e.home_id
 AND r_src.source_kind = 'payload_src'
 AND r_src.source_key = (e.payload::jsonb->>'src');

-- 3) Subject state tables
CREATE TABLE IF NOT EXISTS public.subject_state (
  org_id        text NOT NULL,
  home_id       text NOT NULL,
  subject_id    text NOT NULL,
  state         text NOT NULL,        -- 'present'/'away' (MVP)
  state_since   timestamptz NOT NULL,
  last_event_ts timestamptz,
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, home_id, subject_id)
);

CREATE TABLE IF NOT EXISTS public.subject_state_events (
  event_id    bigserial PRIMARY KEY,
  org_id      text NOT NULL,
  home_id     text NOT NULL,
  subject_id  text NOT NULL,
  prev_state  text,
  new_state   text NOT NULL,
  reason      jsonb,
  computed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_subject_state_events_lookup
ON public.subject_state_events (org_id, home_id, subject_id, computed_at DESC);

-- 4) Compute function (uses events_attributed_v2)
CREATE OR REPLACE FUNCTION public.compute_subject_state_once(
  p_org text,
  p_home text,
  p_present_window_minutes int DEFAULT 60
)
RETURNS TABLE(updated_subjects int, audited_transitions int)
LANGUAGE plpgsql
AS $$
DECLARE
  v_updated int := 0;
  v_audited int := 0;
BEGIN
  WITH
  params AS (
    SELECT make_interval(mins => GREATEST(p_present_window_minutes, 1)) AS present_window
  ),
  clock AS (
    SELECT now() AS now_ts, (now() - (SELECT present_window FROM params)) AS cutoff_ts
  ),
  last_activity AS (
    SELECT org_id, home_id, attributed_subject_id AS subject_id, MAX("timestamp") AS last_ts
    FROM public.events_attributed_v2
    WHERE org_id = p_org AND home_id = p_home
      AND attributed_subject_id IS NOT NULL
      AND category IN ('motion','presence')
    GROUP BY 1,2,3
  ),
  desired AS (
    SELECT la.org_id, la.home_id, la.subject_id,
           CASE WHEN la.last_ts >= (SELECT cutoff_ts FROM clock) THEN 'present' ELSE 'away' END AS new_state,
           la.last_ts
    FROM last_activity la
  ),
  prev AS (
    SELECT s.org_id, s.home_id, s.subject_id, s.state AS prev_state
    FROM public.subject_state s
    WHERE s.org_id = p_org AND s.home_id = p_home
  ),
  upserted AS (
    INSERT INTO public.subject_state (org_id, home_id, subject_id, state, state_since, last_event_ts, updated_at)
    SELECT d.org_id, d.home_id, d.subject_id, d.new_state, now(), d.last_ts, now()
    FROM desired d
    ON CONFLICT (org_id, home_id, subject_id)
    DO UPDATE SET
      state = EXCLUDED.state,
      state_since = CASE WHEN subject_state.state IS DISTINCT FROM EXCLUDED.state
                         THEN EXCLUDED.state_since
                         ELSE subject_state.state_since END,
      last_event_ts = EXCLUDED.last_event_ts,
      updated_at = EXCLUDED.updated_at
    RETURNING 1
  ),
  audited AS (
    INSERT INTO public.subject_state_events (org_id, home_id, subject_id, new_state, prev_state, reason, computed_at)
    SELECT d.org_id, d.home_id, d.subject_id, d.new_state, p.prev_state,
           jsonb_build_object(
             'present_window_minutes', p_present_window_minutes,
             'now', (SELECT now_ts FROM clock),
             'cutoff', (SELECT cutoff_ts FROM clock),
             'last_event_ts', d.last_ts
           ),
           now()
    FROM desired d
    LEFT JOIN prev p ON p.org_id=d.org_id AND p.home_id=d.home_id AND p.subject_id=d.subject_id
    WHERE p.prev_state IS DISTINCT FROM d.new_state
    RETURNING 1
  )
  SELECT (SELECT COUNT(*) FROM upserted), (SELECT COUNT(*) FROM audited)
  INTO v_updated, v_audited;

  updated_subjects := v_updated;
  audited_transitions := v_audited;
  RETURN NEXT;
END;
$$;

-- End.
