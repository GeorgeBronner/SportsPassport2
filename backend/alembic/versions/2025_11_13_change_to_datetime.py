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

    # Check if migration already applied
    columns = [col['name'] for col in inspector.get_columns('games')]
    if 'start_date' in columns:
        # Migration already applied
        return

    # SQLite doesn't support ALTER COLUMN, so we need to:
    # 1. Create new columns
    # 2. Copy data (with conversion)
    # 3. Drop old column (via table recreation)

    # Add new columns
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.add_column(sa.Column('start_date', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('season_type', sa.String(), nullable=True))
        batch_op.create_index(batch_op.f('ix_games_start_date'), ['start_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_games_season_type'), ['season_type'], unique=False)

    # Convert existing date data to datetime (midnight UTC)
    # This is a placeholder - the real data will come from re-importing from API
    op.execute("""
        UPDATE games
        SET start_date = datetime(game_date || ' 00:00:00')
    """)

    # Make start_date NOT NULL after populating it
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.alter_column('start_date', nullable=False)
        # Drop old game_date column
        batch_op.drop_index('ix_games_game_date')
        batch_op.drop_column('game_date')


def downgrade():
    # Recreate game_date column from start_date
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.add_column(sa.Column('game_date', sa.DATE(), nullable=True))
        batch_op.create_index('ix_games_game_date', ['game_date'], unique=False)

    # Convert datetime back to date
    op.execute("""
        UPDATE games
        SET game_date = date(start_date)
    """)

    # Make game_date NOT NULL and drop new columns
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.alter_column('game_date', nullable=False)
        batch_op.drop_index(batch_op.f('ix_games_season_type'))
        batch_op.drop_index(batch_op.f('ix_games_start_date'))
        batch_op.drop_column('season_type')
        batch_op.drop_column('start_date')
