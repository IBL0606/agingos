"""add baseline bootstrap functions for dev setup truth

Revision ID: a8f9c2d1e4b7
Revises: 169d4a5837e0
Create Date: 2026-03-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a8f9c2d1e4b7"
down_revision: Union[str, None] = "169d4a5837e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE OR REPLACE FUNCTION public._baseline_resolve_scope_from_user(
  p_user uuid,
  OUT out_org text,
  OUT out_home text,
  OUT out_subject text
)
RETURNS record
LANGUAGE plpgsql
AS $$
BEGIN
  SELECT s.org_id, s.home_id, s.subject_id
    INTO out_org, out_home, out_subject
  FROM public.api_key_scopes s
  WHERE s.user_id = p_user
    AND s.active = true
  ORDER BY s.updated_at DESC NULLS LAST, s.created_at DESC NULLS LAST
  LIMIT 1;

  IF out_org IS NULL OR out_home IS NULL OR out_subject IS NULL THEN
    out_org := 'default';
    out_home := 'default';
    out_subject := 'default';
  END IF;
END $$;


CREATE OR REPLACE FUNCTION public.build_daily_room_bucket_rollup(
  p_day date,
  p_user uuid
)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  v_org text;
  v_home text;
  v_subject text;
  v_inserted integer := 0;
BEGIN
  SELECT out_org, out_home, out_subject
    INTO v_org, v_home, v_subject
  FROM public._baseline_resolve_scope_from_user(p_user);

  DELETE FROM public.baseline_room_bucket b
  WHERE b.org_id = v_org
    AND b.home_id = v_home
    AND b.subject_id = v_subject
    AND (b.bucket_start AT TIME ZONE 'Europe/Oslo')::date = p_day;

  WITH events_in_day AS (
    SELECT
      e.room_id,
      (
        date_trunc('hour', e."timestamp")
        + (floor(extract(minute from e."timestamp") / 15)::int * interval '15 minute')
      ) AS bucket_start,
      (
        date_trunc('hour', e."timestamp")
        + (floor(extract(minute from e."timestamp") / 15)::int * interval '15 minute')
        + interval '15 minute'
      ) AS bucket_end,
      e.category
    FROM public.events e
    WHERE e.org_id = v_org
      AND e.home_id = v_home
      AND e.subject_id = v_subject
      AND e.stream_id = 'prod'
      AND (e."timestamp" AT TIME ZONE 'Europe/Oslo')::date = p_day
      AND e.room_id IS NOT NULL
      AND e.room_id <> ''
  )
  INSERT INTO public.baseline_room_bucket (
    org_id, home_id, subject_id, room_id,
    bucket_start, bucket_end,
    presence_n, motion_n, door_n
  )
  SELECT
    v_org,
    v_home,
    v_subject,
    t.room_id,
    t.bucket_start,
    t.bucket_end,
    COUNT(*) FILTER (WHERE t.category = 'presence')::int AS presence_n,
    COUNT(*) FILTER (WHERE t.category = 'motion')::int AS motion_n,
    COUNT(*) FILTER (WHERE t.category = 'door')::int AS door_n
  FROM events_in_day t
  GROUP BY t.room_id, t.bucket_start, t.bucket_end
  ORDER BY t.room_id, t.bucket_start;

  GET DIAGNOSTICS v_inserted = ROW_COUNT;
  RETURN v_inserted;
END $$;


CREATE OR REPLACE FUNCTION public.build_daily_transition_rollup(
  p_day date,
  p_user uuid
)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  v_org text;
  v_home text;
  v_subject text;
  v_inserted integer := 0;
BEGIN
  SELECT out_org, out_home, out_subject
    INTO v_org, v_home, v_subject
  FROM public._baseline_resolve_scope_from_user(p_user);

  DELETE FROM public.baseline_transition t
  WHERE t.org_id = v_org
    AND t.home_id = v_home
    AND t.subject_id = v_subject
    AND (t.window_end AT TIME ZONE 'Europe/Oslo')::date = p_day;

  WITH room_events AS (
    SELECT
      e."timestamp" AS ts,
      e.room_id,
      lead(e.room_id) OVER (ORDER BY e."timestamp") AS next_room,
      lead(e."timestamp") OVER (ORDER BY e."timestamp") AS next_ts
    FROM public.events e
    WHERE e.org_id = v_org
      AND e.home_id = v_home
      AND e.subject_id = v_subject
      AND e.stream_id = 'prod'
      AND (e."timestamp" AT TIME ZONE 'Europe/Oslo')::date = p_day
      AND e.room_id IS NOT NULL
      AND e.room_id <> ''
  )
  INSERT INTO public.baseline_transition (
    org_id, home_id, subject_id,
    from_room_id, to_room_id, n,
    window_start, window_end
  )
  SELECT
    v_org,
    v_home,
    v_subject,
    r.room_id,
    r.next_room,
    COUNT(*)::int AS n,
    MIN(r.ts) AS window_start,
    MAX(r.next_ts) AS window_end
  FROM room_events r
  WHERE r.next_room IS NOT NULL
    AND r.room_id <> r.next_room
  GROUP BY r.room_id, r.next_room;

  GET DIAGNOSTICS v_inserted = ROW_COUNT;
  RETURN v_inserted;
END $$;


CREATE OR REPLACE FUNCTION public.build_baseline_7d(
  p_end_day date,
  p_user uuid,
  p_sigma_floor double precision DEFAULT 0.1,
  p_alpha double precision DEFAULT 0.5,
  p_min_days_required integer DEFAULT 3
)
RETURNS TABLE(
  model_start date,
  model_end date,
  baseline_ready boolean,
  days_in_window integer,
  days_with_data integer,
  room_bucket_rows integer,
  room_bucket_supported boolean,
  transition_rows integer,
  transition_supported boolean
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_org text;
  v_home text;
  v_subject text;
  v_start_day date := (p_end_day - 6);
  v_days_with_data integer := 0;
  v_room_rows integer := 0;
  v_transition_rows integer := 0;
  v_ready boolean := false;
BEGIN
  SELECT out_org, out_home, out_subject
    INTO v_org, v_home, v_subject
  FROM public._baseline_resolve_scope_from_user(p_user);

  SELECT COUNT(DISTINCT (e."timestamp" AT TIME ZONE 'Europe/Oslo')::date)::int
    INTO v_days_with_data
  FROM public.events e
  WHERE e.org_id = v_org
    AND e.home_id = v_home
    AND e.subject_id = v_subject
    AND e.stream_id = 'prod'
    AND (e."timestamp" AT TIME ZONE 'Europe/Oslo')::date BETWEEN v_start_day AND p_end_day;

  SELECT COUNT(*)::int
    INTO v_room_rows
  FROM public.baseline_room_bucket b
  WHERE b.org_id = v_org
    AND b.home_id = v_home
    AND b.subject_id = v_subject
    AND (b.bucket_start AT TIME ZONE 'Europe/Oslo')::date BETWEEN v_start_day AND p_end_day;

  SELECT COUNT(*)::int
    INTO v_transition_rows
  FROM public.baseline_transition t
  WHERE t.org_id = v_org
    AND t.home_id = v_home
    AND t.subject_id = v_subject
    AND (t.window_end AT TIME ZONE 'Europe/Oslo')::date BETWEEN v_start_day AND p_end_day;

  v_ready := (v_days_with_data >= GREATEST(p_min_days_required, 0) AND v_room_rows > 0);

  DELETE FROM public.baseline_model_status s
  WHERE s.org_id = v_org
    AND s.home_id = v_home
    AND s.subject_id = v_subject
    AND s.model_end = p_end_day;

  INSERT INTO public.baseline_model_status (
    org_id, home_id, subject_id,
    model_start, model_end,
    baseline_ready, computed_at,
    days_in_window, days_with_data,
    room_bucket_rows, room_bucket_supported,
    transition_rows, transition_supported
  )
  VALUES (
    v_org,
    v_home,
    v_subject,
    v_start_day,
    p_end_day,
    v_ready,
    now(),
    7,
    v_days_with_data,
    v_room_rows,
    (v_room_rows > 0),
    v_transition_rows,
    (v_transition_rows > 0)
  );

  RETURN QUERY
  SELECT
    v_start_day AS model_start,
    p_end_day AS model_end,
    v_ready AS baseline_ready,
    7::int AS days_in_window,
    v_days_with_data AS days_with_data,
    v_room_rows AS room_bucket_rows,
    (v_room_rows > 0) AS room_bucket_supported,
    v_transition_rows AS transition_rows,
    (v_transition_rows > 0) AS transition_supported;
END $$;


CREATE OR REPLACE FUNCTION public.run_baseline_nightly(
  p_user uuid,
  p_sigma_floor double precision DEFAULT 0.1,
  p_alpha double precision DEFAULT 0.5,
  p_min_days_required integer DEFAULT 3
)
RETURNS TABLE(
  user_id uuid,
  model_start date,
  model_end date,
  baseline_ready boolean,
  days_with_data integer,
  room_bucket_rows integer,
  room_bucket_supported integer,
  transition_rows integer,
  transition_supported integer
)
LANGUAGE plpgsql
AS $$
DECLARE
  end_day date := ((now() AT TIME ZONE 'Europe/Oslo')::date - 1);
  d date;
BEGIN
  FOR d IN SELECT generate_series(end_day - 1, end_day, interval '1 day')::date
  LOOP
    PERFORM public.build_daily_room_bucket_rollup(d, p_user);
    PERFORM public.build_daily_transition_rollup(d, p_user);
  END LOOP;

  FOR d IN SELECT generate_series(end_day - 6, end_day, interval '1 day')::date
  LOOP
    PERFORM public.build_daily_room_bucket_rollup(d, p_user);
    PERFORM public.build_daily_transition_rollup(d, p_user);
  END LOOP;

  PERFORM public.build_baseline_7d(end_day, p_user, p_sigma_floor, p_alpha, p_min_days_required);

  RETURN QUERY
  SELECT
    p_user AS user_id,
    s.model_start,
    s.model_end,
    s.baseline_ready,
    s.days_with_data,
    s.room_bucket_rows,
    CASE WHEN s.room_bucket_supported THEN s.room_bucket_rows ELSE 0 END AS room_bucket_supported,
    s.transition_rows,
    CASE WHEN s.transition_supported THEN s.transition_rows ELSE 0 END AS transition_supported
  FROM public.baseline_model_status s
  JOIN public._baseline_resolve_scope_from_user(p_user) r
    ON s.org_id = r.out_org
   AND s.home_id = r.out_home
   AND s.subject_id = r.out_subject
  WHERE s.model_end = end_day;
END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
DROP FUNCTION IF EXISTS public.run_baseline_nightly(uuid, double precision, double precision, integer);
DROP FUNCTION IF EXISTS public.build_baseline_7d(date, uuid, double precision, double precision, integer);
DROP FUNCTION IF EXISTS public.build_daily_transition_rollup(date, uuid);
DROP FUNCTION IF EXISTS public.build_daily_room_bucket_rollup(date, uuid);
DROP FUNCTION IF EXISTS public._baseline_resolve_scope_from_user(uuid);
        """
    )
