"""anomaly episodes table

Revision ID: d3eb1f85b2ba
Revises: 4ff8fe192903
Create Date: 2026-02-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'd3eb1f85b2ba'
down_revision = '4ff8fe192903'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'anomaly_episodes',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),

        sa.Column('room', sa.Text(), nullable=False),
        sa.Column('start_ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_ts', sa.DateTime(timezone=True), nullable=True),

        # Traffic-light level: 0=GREEN, 1=YELLOW, 2=RED
        sa.Column('level', sa.SmallInteger(), nullable=False),

        # Scores (episode aggregate, typically peak or max)
        sa.Column('score_total', sa.Float(), nullable=False),
        sa.Column('score_intensity', sa.Float(), nullable=False),
        sa.Column('score_sequence', sa.Float(), nullable=False),
        sa.Column('score_event', sa.Float(), nullable=False),

        # Peak bucket reference (for evidence snapshot)
        sa.Column('peak_bucket_start_ts', sa.DateTime(timezone=True), nullable=True),
        sa.Column('peak_bucket_score', sa.Float(), nullable=True),

        # Explainability payloads
        sa.Column('reasons', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('peak_bucket_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # How we treated pet/human classification for this episode
        sa.Column('human_weight_mode', sa.Text(), nullable=False, server_default=sa.text("'human_weighted'")),
        sa.Column('pet_weight', sa.Float(), nullable=False, server_default=sa.text('0.25')),

        # Baseline metadata reference (version/window etc.)
        sa.Column('baseline_ref', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    op.create_index('ix_anomaly_episodes_start_ts', 'anomaly_episodes', ['start_ts'])
    op.create_index('ix_anomaly_episodes_room_start_ts', 'anomaly_episodes', ['room', 'start_ts'])
    op.create_index('ix_anomaly_episodes_end_ts', 'anomaly_episodes', ['end_ts'])


def downgrade() -> None:
    op.drop_index('ix_anomaly_episodes_end_ts', table_name='anomaly_episodes')
    op.drop_index('ix_anomaly_episodes_room_start_ts', table_name='anomaly_episodes')
    op.drop_index('ix_anomaly_episodes_start_ts', table_name='anomaly_episodes')
    op.drop_table('anomaly_episodes')
