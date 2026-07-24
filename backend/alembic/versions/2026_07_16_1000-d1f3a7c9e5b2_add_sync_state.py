"""add sync_state

Revision ID: d1f3a7c9e5b2
Revises: c8e2f4a6b1d9
Create Date: 2026-07-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

from sports_passport.db.migration_guards import has_table


# revision identifiers, used by Alembic.
revision = 'd1f3a7c9e5b2'
down_revision = 'c8e2f4a6b1d9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guarded: create_all() built this table on every database the app has
    # booted against, which is ahead of where alembic_version thinks they are.
    if has_table('sync_state'):
        return

    op.create_table(
        'sync_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_status', sa.String(), nullable=True),
        sa.Column('last_games_imported', sa.Integer(), nullable=True),
        sa.Column('last_games_updated', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.Column('last_duration_ms', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['league_id'], ['leagues.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sync_state_id'), 'sync_state', ['id'], unique=False)
    # The model spells this `unique=True, index=True`, i.e. one unique index —
    # not a table constraint plus a plain index. Every existing database has
    # the model's form, since create_all() built them; matching it here keeps a
    # migration-built database identical to a create_all-built one.
    op.create_index(op.f('ix_sync_state_league_id'), 'sync_state', ['league_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_sync_state_league_id'), table_name='sync_state')
    op.drop_index(op.f('ix_sync_state_id'), table_name='sync_state')
    op.drop_table('sync_state')
