"""normalize sync_state.league_id uniqueness to a single unique index

Revision ID: e7a4c9d2b5f1
Revises: a9f2c7e4b8d1
Create Date: 2026-08-10 18:00:00.000000

Every database `d1f3a7c9e5b2` skipped (it returns early on `has_table`,
see that revision's own comment) still carries the pre-migration shape:
a table-level `CONSTRAINT uq_sync_state_league UNIQUE (league_id)` plus a
*non*-unique `ix_sync_state_league_id`, left over from the `create_all()`
era this schema predates (docs/open_issues.md #6). The model spells the
same guarantee as one unique index (`unique=True, index=True`), so those
databases fail `alembic check` forever even though nothing is functionally
wrong (docs/open_issues.md #10).

SQLite can't ALTER a table to drop a named UNIQUE constraint in place, so
this rebuilds `sync_state` via batch mode: reflect the table, drop the old
constraint, drop the old non-unique index, add the unique index the model
declares, copy the data across, swap the table in. Guarded so it is a no-op
on any database already in the current shape (every one built by `create_all`
after issue #6, or by this migration).
"""
from alembic import op
import sqlalchemy as sa

from sports_passport.db.migration_guards import has_table


# revision identifiers, used by Alembic.
revision = 'e7a4c9d2b5f1'
down_revision = 'a9f2c7e4b8d1'
branch_labels = None
depends_on = None

OLD_CONSTRAINT = 'uq_sync_state_league'
INDEX = 'ix_sync_state_league_id'


def upgrade() -> None:
    if not has_table('sync_state'):
        return

    inspector = sa.inspect(op.get_bind())
    has_old_constraint = OLD_CONSTRAINT in {
        uc['name'] for uc in inspector.get_unique_constraints('sync_state')
    }
    index_already_unique = any(
        idx['name'] == INDEX and idx['unique'] for idx in inspector.get_indexes('sync_state')
    )

    if not has_old_constraint and index_already_unique:
        return  # already the current shape

    with op.batch_alter_table('sync_state', recreate='always') as batch_op:
        if has_old_constraint:
            batch_op.drop_constraint(OLD_CONSTRAINT, type_='unique')
        if not index_already_unique:
            batch_op.drop_index(INDEX)
            batch_op.create_index(INDEX, ['league_id'], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    has_old_constraint = OLD_CONSTRAINT in {
        uc['name'] for uc in inspector.get_unique_constraints('sync_state')
    }
    if has_old_constraint:
        return  # already the pre-migration shape

    with op.batch_alter_table('sync_state', recreate='always') as batch_op:
        batch_op.drop_index(INDEX)
        batch_op.create_index(INDEX, ['league_id'], unique=False)
        batch_op.create_unique_constraint(OLD_CONSTRAINT, ['league_id'])
