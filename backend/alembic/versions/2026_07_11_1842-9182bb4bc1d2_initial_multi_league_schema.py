"""initial multi-league schema

Revision ID: 9182bb4bc1d2
Revises:
Create Date: 2026-07-11 18:42:07.045813

Backfilled 2026-07-23. This revision shipped as an empty `pass` stub, so the
schema was only ever created by `Base.metadata.create_all()` in main.py and a
fresh `alembic upgrade head` died at the first ALTER TABLE with "no such table".
The tables below are the schema *as of this revision* — deliberately without
teams.logo_url, venues.latitude/longitude, sync_state, password_reset_tokens
and the attendance unique index, each of which belongs to a later revision.

Every step is guarded: existing databases already have these tables, and this
has to be a no-op there rather than an error.
"""
from alembic import op
import sqlalchemy as sa

from sports_passport.db.migration_guards import has_table


# revision identifiers, used by Alembic.
revision = '9182bb4bc1d2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Order matters: leagues and venues before teams/games, games before
    # attendance. SQLite tolerates forward references; PostgreSQL would not.
    if not has_table('users'):
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(), nullable=False),
            sa.Column('password_hash', sa.String(), nullable=False),
            sa.Column('full_name', sa.String(), nullable=False),
            sa.Column('is_admin', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_users_id', 'users', ['id'])
        op.create_index('ix_users_email', 'users', ['email'], unique=True)

    if not has_table('leagues'):
        op.create_table(
            'leagues',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('code', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('sport', sa.String(), nullable=False),
            sa.Column('active', sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_leagues_id', 'leagues', ['id'])
        op.create_index('ix_leagues_code', 'leagues', ['code'], unique=True)

    if not has_table('venues'):
        op.create_table(
            'venues',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('city', sa.String()),
            sa.Column('state', sa.String()),
            sa.Column('country', sa.String()),
            sa.Column('capacity', sa.Integer()),
            sa.Column('source', sa.String(), nullable=False),
            sa.Column('source_venue_id', sa.String()),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('source', 'source_venue_id', name='uq_venue_source'),
        )
        for col in ('id', 'name', 'city', 'state', 'source', 'source_venue_id'):
            op.create_index(f'ix_venues_{col}', 'venues', [col])

    if not has_table('teams'):
        op.create_table(
            'teams',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('league_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('nickname', sa.String()),
            sa.Column('abbreviation', sa.String()),
            sa.Column('city', sa.String()),
            sa.Column('state', sa.String()),
            sa.Column('conference', sa.String()),
            sa.Column('division', sa.String()),
            sa.Column('classification', sa.String()),
            sa.Column('first_season', sa.Integer()),
            sa.Column('last_season', sa.Integer()),
            sa.Column('franchise_id', sa.Integer()),
            sa.Column('source', sa.String(), nullable=False),
            sa.Column('source_team_id', sa.String()),
            sa.ForeignKeyConstraint(['league_id'], ['leagues.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('source', 'source_team_id', name='uq_team_source'),
        )
        for col in ('id', 'league_id', 'name', 'abbreviation', 'conference',
                    'classification', 'franchise_id', 'source', 'source_team_id'):
            op.create_index(f'ix_teams_{col}', 'teams', [col])

    if not has_table('games'):
        op.create_table(
            'games',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('league_id', sa.Integer(), nullable=False),
            sa.Column('home_team_id', sa.Integer(), nullable=False),
            sa.Column('away_team_id', sa.Integer(), nullable=False),
            sa.Column('home_score', sa.Integer()),
            sa.Column('away_score', sa.Integer()),
            sa.Column('start_date', sa.DateTime(), nullable=False),
            sa.Column('has_time', sa.Boolean(), nullable=False),
            sa.Column('season', sa.Integer(), nullable=False),
            sa.Column('season_type', sa.String()),
            sa.Column('week', sa.Integer()),
            sa.Column('venue_id', sa.Integer()),
            sa.Column('neutral_site', sa.Boolean(), nullable=False),
            sa.Column('attendance', sa.Integer()),
            sa.Column('overtime_flag', sa.String()),
            sa.Column('source', sa.String(), nullable=False),
            sa.Column('source_game_id', sa.String(), nullable=False),
            sa.ForeignKeyConstraint(['league_id'], ['leagues.id']),
            sa.ForeignKeyConstraint(['home_team_id'], ['teams.id']),
            sa.ForeignKeyConstraint(['away_team_id'], ['teams.id']),
            sa.ForeignKeyConstraint(['venue_id'], ['venues.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('source', 'source_game_id', name='uq_game_source'),
        )
        for col in ('id', 'league_id', 'home_team_id', 'away_team_id', 'start_date',
                    'season', 'season_type', 'week', 'venue_id', 'source', 'source_game_id'):
            op.create_index(f'ix_games_{col}', 'games', [col])

    if not has_table('user_game_attendance'):
        op.create_table(
            'user_game_attendance',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('game_id', sa.Integer(), nullable=False),
            sa.Column('notes', sa.String()),
            sa.Column('created_at', sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['game_id'], ['games.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        for col in ('id', 'user_id', 'game_id'):
            op.create_index(f'ix_user_game_attendance_{col}', 'user_game_attendance', [col])


def downgrade() -> None:
    # Unguarded on purpose: a downgrade is deliberate and should fail loudly
    # if what it removes isn't there. Reverse dependency order.
    for table in ('user_game_attendance', 'games', 'teams', 'venues', 'leagues', 'users'):
        op.drop_table(table)
