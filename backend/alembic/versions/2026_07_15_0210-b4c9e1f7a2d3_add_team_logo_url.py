"""add team logo_url

Revision ID: b4c9e1f7a2d3
Revises: 9182bb4bc1d2
Create Date: 2026-07-15 02:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4c9e1f7a2d3'
down_revision = '9182bb4bc1d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('teams', sa.Column('logo_url', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('teams') as batch_op:
        batch_op.drop_column('logo_url')
