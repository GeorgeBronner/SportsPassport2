"""add venue coordinates

Revision ID: c8e2f4a6b1d9
Revises: b4c9e1f7a2d3
Create Date: 2026-07-15 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8e2f4a6b1d9'
down_revision = 'b4c9e1f7a2d3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('venues', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('venues', sa.Column('longitude', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('venues') as batch_op:
        batch_op.drop_column('longitude')
        batch_op.drop_column('latitude')
