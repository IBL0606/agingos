"""merge heads for anomaly episodes

Revision ID: 7784729f5c7e
Revises: 06a6a5dc2ab1, d3eb1f85b2ba
Create Date: 2026-02-05 05:15:02.275906

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7784729f5c7e'
down_revision: Union[str, None] = ('06a6a5dc2ab1', 'd3eb1f85b2ba')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
