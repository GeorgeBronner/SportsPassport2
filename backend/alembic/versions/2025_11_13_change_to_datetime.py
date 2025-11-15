"""Change game_date to start_date datetime and add season_type

Revision ID: 2025_11_13_datetime
Revises:
Create Date: 2025-11-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '2025_11_13_datetime'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Check if games table exists
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'games' not in tables:
        # Database is empty, skip this migration
        # Tables will be created from models
        return

    # === GAMES TABLE MIGRATION ===
    games_columns = [col['name'] for col in inspector.get_columns('games')]

    # Only migrate if we still have the old schema
    if 'game_date' in games_columns and 'start_date' not in games_columns:
        # Step 1: Add new columns (simpler approach - no batch operation)
        op.add_column('games', sa.Column('start_date', sa.DateTime(), nullable=True))
        op.add_column('games', sa.Column('season_type', sa.String(), nullable=True))

        # Step 2: Convert existing date data to datetime (midnight UTC)
        op.execute("""
            UPDATE games
            SET start_date = datetime(game_date || ' 00:00:00')
        """)

        # Step 3: Create indexes on new columns
        op.create_index('ix_games_start_date', 'games', ['start_date'])
        op.create_index('ix_games_season_type', 'games', ['season_type'])

        # Step 4: Drop old game_date column and index using batch operation
        # (SQLite requires recreating table to drop columns)
        with op.batch_alter_table('games', schema=None) as batch_op:
            batch_op.drop_index('ix_games_game_date')
            batch_op.drop_column('game_date')

    # === TEAMS TABLE MIGRATION ===
    teams_columns = [col['name'] for col in inspector.get_columns('teams')]

    if 'classification' not in teams_columns:
        # Add classification column to teams
        op.add_column('teams', sa.Column('classification', sa.String(), nullable=True))

        # Set default value for existing teams
        op.execute("UPDATE teams SET classification = 'fbs'")

        # Create index
        op.create_index('ix_teams_classification', 'teams', ['classification'])


def downgrade():
    # === REVERT TEAMS TABLE ===
    op.drop_index('ix_teams_classification', 'teams')
    with op.batch_alter_table('teams', schema=None) as batch_op:
        batch_op.drop_column('classification')

    # === REVERT GAMES TABLE ===
    # Recreate game_date column from start_date
    op.add_column('games', sa.Column('game_date', sa.DATE(), nullable=True))

    # Convert datetime back to date
    op.execute("""
        UPDATE games
        SET game_date = date(start_date)
    """)

    # Create index on game_date
    op.create_index('ix_games_game_date', 'games', ['game_date'])

    # Drop new columns using batch operation
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.drop_index('ix_games_season_type')
        batch_op.drop_index('ix_games_start_date')
        batch_op.drop_column('season_type')
        batch_op.drop_column('start_date')
