"""normalize password_reset_tokens indexes

Revision ID: b2c6d1e8f4a7
Revises: e7a4c9d2b5f1
Create Date: 2026-08-13 09:00:00.000000

Every database this schema has ever booted against carries `token_hash` as
an inline, unnamed `UNIQUE` constraint (from `sa.UniqueConstraint('token_hash')`
in e2f5b8c3d4a1's create_table) *plus* a separate non-unique
`ix_password_reset_tokens_token_hash` index on the same column — two
structures for one uniqueness guarantee, diverging from the single
`unique=True, index=True` pattern the rest of the schema uses (e.g.
`users.email`). Separately, `user_id` — filtered on every forgot-password
request — has never had an index at all.

SQLite can't ALTER a table to drop an unnamed constraint by name, so this
rebuilds `password_reset_tokens` via batch mode with a `naming_convention`
override that gives the reflected constraint a deterministic name to target
(confirmed live: `get_unique_constraints` reports `name: None` for it).
Guarded so it is a no-op on any database already in the target shape.
"""
from alembic import op
import sqlalchemy as sa

from sports_passport.db.migration_guards import has_table


# revision identifiers, used by Alembic.
revision = 'b2c6d1e8f4a7'
down_revision = 'e7a4c9d2b5f1'
branch_labels = None
depends_on = None

OLD_INDEX = 'ix_password_reset_tokens_token_hash'
SYNTHETIC_UQ_NAME = 'uq_password_reset_tokens_token_hash'
USER_ID_INDEX = 'ix_password_reset_tokens_user_id'
NAMING_CONVENTION = {'uq': 'uq_%(table_name)s_%(column_0_name)s'}


def upgrade() -> None:
    if not has_table('password_reset_tokens'):
        return

    inspector = sa.inspect(op.get_bind())
    indexes = {i['name']: i for i in inspector.get_indexes('password_reset_tokens')}
    token_hash_is_unique = indexes.get(OLD_INDEX, {}).get('unique')
    has_user_id_index = USER_ID_INDEX in indexes
    has_inline_unique = any(
        uc['column_names'] == ['token_hash']
        for uc in inspector.get_unique_constraints('password_reset_tokens')
    )

    if token_hash_is_unique and has_user_id_index and not has_inline_unique:
        return  # already the current shape

    with op.batch_alter_table(
        'password_reset_tokens', recreate='always', naming_convention=NAMING_CONVENTION
    ) as batch_op:
        if has_inline_unique:
            if not token_hash_is_unique:
                batch_op.drop_index(OLD_INDEX)
            batch_op.drop_constraint(SYNTHETIC_UQ_NAME, type_='unique')
            batch_op.create_index(OLD_INDEX, ['token_hash'], unique=True)
        if not has_user_id_index:
            batch_op.create_index(USER_ID_INDEX, ['user_id'])


def downgrade() -> None:
    if not has_table('password_reset_tokens'):
        return

    with op.batch_alter_table('password_reset_tokens', recreate='always') as batch_op:
        batch_op.drop_index(USER_ID_INDEX)
        batch_op.drop_index(OLD_INDEX)
        batch_op.create_unique_constraint(SYNTHETIC_UQ_NAME, ['token_hash'])
        batch_op.create_index(OLD_INDEX, ['token_hash'], unique=False)
