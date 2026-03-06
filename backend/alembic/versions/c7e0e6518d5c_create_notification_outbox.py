"""create notification_outbox

Revision ID: c7e0e6518d5c
Revises: 16675adff372
Create Date: 2026-03-05 05:18:42.912522

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e0e6518d5c'
down_revision: Union[str, None] = '16675adff372'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent DDL (safe on dev + CI re-runs)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.notification_outbox (
          id               bigserial PRIMARY KEY,
          org_id           text NOT NULL,
          home_id          text NOT NULL,
          subject_id       text NOT NULL,

          route_type       text NOT NULL DEFAULT 'db',
          route_key        text,
          destination      text,

          message_type     text NOT NULL DEFAULT 'GENERIC',
          severity         text NOT NULL DEFAULT 'INFO',

          idempotency_key  text,
          payload          jsonb NOT NULL DEFAULT '{}'::jsonb,

          bypass_policy    boolean NOT NULL DEFAULT false,

          status           text NOT NULL DEFAULT 'PENDING',
          attempt_n        integer NOT NULL DEFAULT 0,
          max_attempts     integer NOT NULL DEFAULT 10,

          next_attempt_at  timestamptz NOT NULL DEFAULT now(),
          last_attempt_at  timestamptz,
          delivered_at     timestamptz,
          acked_at         timestamptz,

          locked_at        timestamptz,
          locked_by        text,

          created_at       timestamptz NOT NULL DEFAULT now(),
          updated_at       timestamptz NOT NULL DEFAULT now(),

          CONSTRAINT notification_outbox_status_check
            CHECK (status IN ('PENDING','RETRY','IN_FLIGHT','DELIVERED','ACKED','DEAD'))
        );

        CREATE INDEX IF NOT EXISTS ix_notification_outbox_due
          ON public.notification_outbox (status, next_attempt_at, id);

        CREATE INDEX IF NOT EXISTS ix_notification_outbox_locked
          ON public.notification_outbox (locked_at);

        CREATE UNIQUE INDEX IF NOT EXISTS ux_notification_outbox_idempotency_key
          ON public.notification_outbox (idempotency_key)
          WHERE idempotency_key IS NOT NULL AND idempotency_key <> '';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS public.ux_notification_outbox_idempotency_key;
        DROP INDEX IF EXISTS public.ix_notification_outbox_locked;
        DROP INDEX IF EXISTS public.ix_notification_outbox_due;
        DROP TABLE IF EXISTS public.notification_outbox;
        """
    )
