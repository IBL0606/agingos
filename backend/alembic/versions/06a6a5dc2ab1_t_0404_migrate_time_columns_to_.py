"""T-0404: migrate time columns to timestamptz

Revision ID: 06a6a5dc2ab1
Revises: 32bf5b5e9e5f
Create Date: 2025-12-22 21:13:28.133312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06a6a5dc2ab1'
down_revision: Union[str, None] = '32bf5b5e9e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Interpret existing naive timestamps as UTC, convert to timestamptz
    op.execute("""
        ALTER TABLE events
        ALTER COLUMN timestamp TYPE timestamptz
        USING (timestamp AT TIME ZONE 'UTC');
    """)

    op.execute("""
        ALTER TABLE deviations
        ALTER COLUMN started_at TYPE timestamptz
        USING (started_at AT TIME ZONE 'UTC');
    """)
    op.execute("""
        ALTER TABLE deviations
        ALTER COLUMN last_seen_at TYPE timestamptz
        USING (last_seen_at AT TIME ZONE 'UTC');
    """)

    op.execute("""
        ALTER TABLE rules
        ALTER COLUMN created_at TYPE timestamptz
        USING (created_at AT TIME ZONE 'UTC');
    """)


def downgrade() -> None:
    # Convert timestamptz back to naive UTC (drop tzinfo, keep instant in UTC)
    op.execute("""
        ALTER TABLE events
        ALTER COLUMN timestamp TYPE timestamp without time zone
        USING (timestamp AT TIME ZONE 'UTC');
    """)

    op.execute("""
        ALTER TABLE deviations
        ALTER COLUMN started_at TYPE timestamp without time zone
        USING (started_at AT TIME ZONE 'UTC');
    """)
    op.execute("""
        ALTER TABLE deviations
        ALTER COLUMN last_seen_at TYPE timestamp without time zone
        USING (last_seen_at AT TIME ZONE 'UTC');
    """)

    op.execute("""
        ALTER TABLE rules
        ALTER COLUMN created_at TYPE timestamp without time zone
        USING (created_at AT TIME ZONE 'UTC');
    """)

