BEGIN;

-- 1) Audit table for notification_policy (P1-6-2)
CREATE TABLE IF NOT EXISTS public.notification_policy_events (
  id bigserial PRIMARY KEY,
  org_id text NOT NULL,
  home_id text NOT NULL,
  subject_id text NOT NULL,
  action text NOT NULL CHECK (action IN ('INSERT','UPDATE','DELETE')),
  changed_at timestamptz NOT NULL DEFAULT now(),
  actor text NULL,
  prev jsonb NULL,
  next jsonb NULL
);

CREATE INDEX IF NOT EXISTS notification_policy_events_scope_ts_idx
  ON public.notification_policy_events (org_id, home_id, subject_id, changed_at DESC);

-- 2) Trigger function (writes one audit row per change)
CREATE OR REPLACE FUNCTION public.trg_notification_policy_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF (TG_OP = 'INSERT') THEN
    INSERT INTO public.notification_policy_events(org_id,home_id,subject_id,action,actor,prev,next)
    VALUES (NEW.org_id, NEW.home_id, NEW.subject_id, 'INSERT', NEW.updated_by, NULL, to_jsonb(NEW));
    RETURN NEW;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO public.notification_policy_events(org_id,home_id,subject_id,action,actor,prev,next)
    VALUES (NEW.org_id, NEW.home_id, NEW.subject_id, 'UPDATE', NEW.updated_by, to_jsonb(OLD), to_jsonb(NEW));
    RETURN NEW;
  ELSIF (TG_OP = 'DELETE') THEN
    INSERT INTO public.notification_policy_events(org_id,home_id,subject_id,action,actor,prev,next)
    VALUES (OLD.org_id, OLD.home_id, OLD.subject_id, 'DELETE', OLD.updated_by, to_jsonb(OLD), NULL);
    RETURN OLD;
  END IF;
  RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS notification_policy_audit_trg ON public.notification_policy;
CREATE TRIGGER notification_policy_audit_trg
AFTER INSERT OR UPDATE OR DELETE ON public.notification_policy
FOR EACH ROW
EXECUTE FUNCTION public.trg_notification_policy_audit();

-- 3) Helper for "partner override" (P1-6-1) = set override_until safely via upsert
-- (worker støtter allerede override_until)
CREATE OR REPLACE FUNCTION public.set_notification_policy_override(
  p_org text,
  p_home text,
  p_subject text,
  p_override_until timestamptz,
  p_updated_by text
)
RETURNS TABLE (
  org_id text,
  home_id text,
  subject_id text,
  override_until timestamptz,
  updated_at timestamptz,
  updated_by text
)
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO public.notification_policy(org_id, home_id, subject_id, override_until, updated_by)
  VALUES (p_org, p_home, p_subject, p_override_until, p_updated_by)
  ON CONFLICT ON CONSTRAINT notification_policy_pkey DO UPDATE
  SET override_until = EXCLUDED.override_until,
      updated_at = now(),
      updated_by = EXCLUDED.updated_by;

  RETURN QUERY
  SELECT np.org_id, np.home_id, np.subject_id, np.override_until, np.updated_at, np.updated_by
  FROM public.notification_policy np
  WHERE np.org_id=p_org AND np.home_id=p_home AND np.subject_id=p_subject;
END;
$$;

COMMIT;
