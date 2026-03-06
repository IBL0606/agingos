"""create rooms and sensor_room_map

Revision ID: 169d4a5837e0
Revises: c7e0e6518d5c
Create Date: 2026-03-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "169d4a5837e0"
down_revision: Union[str, None] = "c7e0e6518d5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.rooms (
          org_id        text NOT NULL,
          home_id       text NOT NULL,
          room_id       text NOT NULL,
          display_name  text NOT NULL,
          room_type     text NOT NULL DEFAULT 'OTHER',
          created_at    timestamptz NOT NULL DEFAULT now(),
          updated_at    timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (org_id, home_id, room_id)
        );

        CREATE INDEX IF NOT EXISTS ix_rooms_scope
          ON public.rooms (org_id, home_id);

        CREATE TABLE IF NOT EXISTS public.sensor_room_map (
          org_id        text NOT NULL,
          home_id       text NOT NULL,
          entity_id     text NOT NULL,
          room_id       text NOT NULL,
          active        boolean NOT NULL DEFAULT true,
          note          text NULL,
          created_at    timestamptz NOT NULL DEFAULT now(),
          updated_at    timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (org_id, home_id, entity_id),
          CONSTRAINT fk_sensor_room_map_room
            FOREIGN KEY (org_id, home_id, room_id)
            REFERENCES public.rooms (org_id, home_id, room_id)
            ON UPDATE CASCADE
            ON DELETE RESTRICT
        );

        CREATE INDEX IF NOT EXISTS ix_sensor_room_map_scope
          ON public.sensor_room_map (org_id, home_id);

        CREATE INDEX IF NOT EXISTS ix_sensor_room_map_room
          ON public.sensor_room_map (org_id, home_id, room_id)
          WHERE active = true;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS public.sensor_room_map;
        DROP TABLE IF EXISTS public.rooms;
        """
    )
