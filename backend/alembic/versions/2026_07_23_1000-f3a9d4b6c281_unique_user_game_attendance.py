"""unique index on (user_id, game_id) for attendance

Revision ID: f3a9d4b6c281
Revises: e2f5b8c3d4a1
Create Date: 2026-07-23 10:00:00.000000

The routers already reject a second attendance row for the same game, but that
check-then-insert is racy under concurrent requests. Enforce it in the schema.
Any duplicates that slipped through are collapsed first, keeping the oldest row
(lowest id) and its notes.
"""
from alembic import op
import sqlalchemy as sa

from sports_passport.db.migration_guards import has_index


# revision identifiers, used by Alembic.
revision = 'f3a9d4b6c281'
down_revision = 'e2f5b8c3d4a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guarded: the model declares this index too, so create_all() will have
    # built it on any database the app booted before this migration ran.
    if has_index('user_game_attendance', 'uq_user_game_attendance'):
        return

    # No guard needed on the dedupe itself — it keeps MIN(id) per pair and is
    # a no-op where there are no duplicates.
    op.execute(
        sa.text(
            """
            DELETE FROM user_game_attendance
            WHERE id NOT IN (
                SELECT MIN(id) FROM user_game_attendance GROUP BY user_id, game_id
            )
            """
        )
    )
    op.create_index(
        'uq_user_game_attendance',
        'user_game_attendance',
        ['user_id', 'game_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_user_game_attendance', table_name='user_game_attendance')
