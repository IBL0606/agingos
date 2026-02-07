"""create proposals + proposal_actions

Revision ID: 5d205e6bbb78
Revises: 7784729f5c7e
Create Date: 20260205_155323
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "5d205e6bbb78"
down_revision = "7784729f5c7e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TABLE IF NOT EXISTS proposals (\n  proposal_id        BIGSERIAL PRIMARY KEY,\n\n  org_id             TEXT NOT NULL,\n  subject_id         TEXT NOT NULL,\n  room_id            TEXT NULL,\n\n  proposal_type      TEXT NOT NULL,\n  dedupe_key         TEXT NOT NULL,\n\n  state              TEXT NOT NULL DEFAULT 'NEW'\n                      CHECK (state IN ('NEW','TESTING','ACTIVE','REJECTED')),\n  priority           INT  NOT NULL DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),\n\n  evidence           JSONB NOT NULL DEFAULT '{}'::jsonb,\n  why                JSONB NOT NULL DEFAULT '[]'::jsonb,\n\n  action_target      TEXT  NOT NULL,\n  action_payload     JSONB NOT NULL DEFAULT '{}'::jsonb,\n\n  first_detected_at  TIMESTAMPTZ NOT NULL DEFAULT now(),\n  last_detected_at   TIMESTAMPTZ NOT NULL DEFAULT now(),\n  window_start       TIMESTAMPTZ NULL,\n  window_end         TIMESTAMPTZ NULL,\n\n  test_started_at    TIMESTAMPTZ NULL,\n  test_until         TIMESTAMPTZ NULL,\n\n  activated_at       TIMESTAMPTZ NULL,\n  rejected_at        TIMESTAMPTZ NULL,\n\n  last_actor         TEXT NULL,\n  last_source        TEXT NULL,\n  last_note          TEXT NULL,\n\n  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),\n  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()\n);\n\nCREATE OR REPLACE FUNCTION trg_set_updated_at()\nRETURNS TRIGGER AS $$\nBEGIN\n  NEW.updated_at = now();\n  RETURN NEW;\nEND;\n$$ LANGUAGE plpgsql;\n\nDROP TRIGGER IF EXISTS set_updated_at_proposals ON proposals;\nCREATE TRIGGER set_updated_at_proposals\nBEFORE UPDATE ON proposals\nFOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();\n\nCREATE UNIQUE INDEX IF NOT EXISTS ux_proposals_open_dedupe\nON proposals(org_id, subject_id, proposal_type, dedupe_key)\nWHERE state IN ('NEW','TESTING','ACTIVE');\n\nCREATE INDEX IF NOT EXISTS ix_proposals_last_detected\nON proposals(org_id, subject_id, last_detected_at DESC);\n\nCREATE INDEX IF NOT EXISTS ix_proposals_state\nON proposals(org_id, subject_id, state);\n\nCREATE TABLE IF NOT EXISTS proposal_actions (\n  action_id     BIGSERIAL PRIMARY KEY,\n  proposal_id   BIGINT NOT NULL REFERENCES proposals(proposal_id) ON DELETE CASCADE,\n\n  action        TEXT NOT NULL CHECK (action IN ('TEST','ACTIVATE','REJECT','AUTO_EXPIRE_TEST')),\n  prev_state    TEXT NOT NULL,\n  new_state     TEXT NOT NULL,\n\n  actor         TEXT NULL,\n  source        TEXT NOT NULL DEFAULT 'system',\n  note          TEXT NULL,\n\n  payload       JSONB NOT NULL DEFAULT '{}'::jsonb,\n  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()\n);\n\nCREATE INDEX IF NOT EXISTS ix_proposal_actions_pid_time\nON proposal_actions(proposal_id, created_at DESC);")


def downgrade() -> None:
    # MVP: best-effort reverse (drop in correct order)
    op.execute("DROP TABLE IF EXISTS proposal_actions;")
    op.execute("DROP TRIGGER IF EXISTS set_updated_at_proposals ON proposals;")
    op.execute("DROP FUNCTION IF EXISTS trg_set_updated_at();")
    op.execute("DROP TABLE IF EXISTS proposals;")
