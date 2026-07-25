"""add team logo_url

Revision ID: b4c9e1f7a2d3
Revises: 9182bb4bc1d2
Create Date: 2026-07-15 02:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

from sports_passport.db.base_schema import create_base_schema
from sports_passport.db.migration_guards import has_column


# revision identifiers, used by Alembic.
revision = 'b4c9e1f7a2d3'
down_revision = '9182bb4bc1d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The old chain committed the empty `9182bb4bc1d2` stub and then died here,
    # leaving fresh databases stamped one revision *past* the schema they never
    # got. Alembic starts such a database at this revision, so repairing the
    # base schema has to happen here — backfilling the root alone never runs
    # for them. No-op everywhere else.
    create_base_schema()

    # Guarded: create_all() built this column on every existing database.
    if not has_column('teams', 'logo_url'):
        op.add_column('teams', sa.Column('logo_url', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('teams') as batch_op:
        batch_op.drop_column('logo_url')
