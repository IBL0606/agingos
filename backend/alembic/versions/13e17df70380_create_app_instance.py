"""create app_instance

Revision ID: 13e17df70380
Revises: 5d205e6bbb78
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "13e17df70380"
down_revision = "5d205e6bbb78"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure uuid generator exists (Postgres)
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    op.create_table(
        "app_instance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
    )

    # Ensure exactly one row exists so backend can resolve user_id
    op.execute("INSERT INTO app_instance DEFAULT VALUES;")

def downgrade() -> None:
    op.drop_table("app_instance")
