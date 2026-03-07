"""create notification_deliveries table

Revision ID: 1f2b3c4d5e6f
Revises: 9c5f1a2b7e44
Create Date: 2026-03-06 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '1f2b3c4d5e6f'
down_revision: Union[str, None] = '9c5f1a2b7e44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.notification_deliveries (
          id bigserial PRIMARY KEY,
          outbox_id bigint NOT NULL,
          org_id text NOT NULL,
          home_id text NOT NULL,
          subject_id text NOT NULL,
          route_type text NOT NULL,
          route_key text NOT NULL,
          idempotency_key text NOT NULL,
          provider_msg_id text NULL,
          response jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE UNIQUE INDEX IF NOT EXISTS ux_notification_deliveries_dedupe
          ON public.notification_deliveries (
            org_id, home_id, subject_id, route_type, route_key, idempotency_key
          );

        CREATE INDEX IF NOT EXISTS ix_notification_deliveries_outbox
          ON public.notification_deliveries (outbox_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS public.ix_notification_deliveries_outbox;
        DROP INDEX IF EXISTS public.ux_notification_deliveries_dedupe;
        DROP TABLE IF EXISTS public.notification_deliveries;
        """
    )
