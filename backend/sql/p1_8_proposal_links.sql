-- P1-8: proposal_links (productized schema)
-- Source: extracted from live DB (public.proposal_links) via pg_dump --schema-only.
-- Purpose: Link proposals to exactly one "source" entity (deviation OR episode OR anomaly_episode).
-- Scope: org_id/home_id/subject_id enforced via columns + FKs (P0-2 hygiene).

CREATE TABLE IF NOT EXISTS public.proposal_links (
    link_id bigint NOT NULL,
    org_id text NOT NULL,
    home_id text NOT NULL,
    subject_id text NOT NULL,
    proposal_id bigint NOT NULL,
    deviation_id integer,
    episode_id uuid,
    anomaly_episode_id bigint,
    link_type text DEFAULT 'DERIVED'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT proposal_links_exactly_one_target CHECK ((((CASE WHEN (deviation_id IS NULL) THEN 0 ELSE 1 END +
        CASE WHEN (episode_id IS NULL) THEN 0 ELSE 1 END) +
        CASE WHEN (anomaly_episode_id IS NULL) THEN 0 ELSE 1 END) = 1))
);

-- Sequence for link_id
CREATE SEQUENCE IF NOT EXISTS public.proposal_links_link_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.proposal_links_link_id_seq OWNED BY public.proposal_links.link_id;

ALTER TABLE ONLY public.proposal_links
  ALTER COLUMN link_id SET DEFAULT nextval('public.proposal_links_link_id_seq'::regclass);

-- PK
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='proposal_links_pkey' AND conrelid='public.proposal_links'::regclass
  ) THEN
    ALTER TABLE ONLY public.proposal_links
      ADD CONSTRAINT proposal_links_pkey PRIMARY KEY (link_id);
  END IF;
END$$;

-- Indexes
CREATE INDEX IF NOT EXISTS ix_proposal_links_scope_created
  ON public.proposal_links (org_id, home_id, subject_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_proposal_links_scope_proposal
  ON public.proposal_links (org_id, home_id, subject_id, proposal_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_proposal_links_scope_proposal_anom
  ON public.proposal_links (org_id, home_id, subject_id, proposal_id, anomaly_episode_id)
  WHERE (anomaly_episode_id IS NOT NULL);

CREATE UNIQUE INDEX IF NOT EXISTS ux_proposal_links_scope_proposal_deviation
  ON public.proposal_links (org_id, home_id, subject_id, proposal_id, deviation_id)
  WHERE (deviation_id IS NOT NULL);

CREATE UNIQUE INDEX IF NOT EXISTS ux_proposal_links_scope_proposal_episode
  ON public.proposal_links (org_id, home_id, subject_id, proposal_id, episode_id)
  WHERE (episode_id IS NOT NULL);

-- FKs (scope-aware) with ON DELETE CASCADE
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='proposal_links_anom_scope_fkey') THEN
    ALTER TABLE ONLY public.proposal_links
      ADD CONSTRAINT proposal_links_anom_scope_fkey
      FOREIGN KEY (anomaly_episode_id, org_id, home_id, subject_id)
      REFERENCES public.anomaly_episodes(id, org_id, home_id, subject_id)
      ON DELETE CASCADE;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='proposal_links_deviation_scope_fkey') THEN
    ALTER TABLE ONLY public.proposal_links
      ADD CONSTRAINT proposal_links_deviation_scope_fkey
      FOREIGN KEY (deviation_id, org_id, home_id, subject_id)
      REFERENCES public.deviations(id, org_id, home_id, subject_id)
      ON DELETE CASCADE;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='proposal_links_episode_scope_fkey') THEN
    ALTER TABLE ONLY public.proposal_links
      ADD CONSTRAINT proposal_links_episode_scope_fkey
      FOREIGN KEY (episode_id, org_id, home_id, subject_id)
      REFERENCES public.episodes(id, org_id, home_id, subject_id)
      ON DELETE CASCADE;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='proposal_links_proposal_scope_fkey') THEN
    ALTER TABLE ONLY public.proposal_links
      ADD CONSTRAINT proposal_links_proposal_scope_fkey
      FOREIGN KEY (proposal_id, org_id, home_id, subject_id)
      REFERENCES public.proposals(proposal_id, org_id, home_id, subject_id)
      ON DELETE CASCADE;
  END IF;
END$$;
