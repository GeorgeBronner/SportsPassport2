"""initial multi-league schema

Revision ID: 9182bb4bc1d2
Revises:
Create Date: 2026-07-11 18:42:07.045813

Backfilled 2026-07-23. This revision shipped as an empty `pass` stub, so the
schema was only ever created by `Base.metadata.create_all()` in main.py and a
fresh `alembic upgrade head` died at the first ALTER TABLE with "no such table".

The table definitions live in `sports_passport.db.base_schema` because
`b4c9e1f7a2d3` needs them too: databases stamped at this revision by the old
empty stub are already *past* it, so backfilling here alone would never reach
them. See that module for the full reasoning.

`create_base_schema()` is guarded per table: existing databases already have
these, and this has to be a no-op there rather than an error.
"""
from alembic import op

from sports_passport.db.base_schema import create_base_schema


# revision identifiers, used by Alembic.
revision = '9182bb4bc1d2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_base_schema()


def downgrade() -> None:
    # Unguarded on purpose: a downgrade is deliberate and should fail loudly
    # if what it removes isn't there. Reverse dependency order.
    for table in ('user_game_attendance', 'games', 'teams', 'venues', 'leagues', 'users'):
        op.drop_table(table)
