"""add sync_state.last_success_at

Revision ID: a7e4c2f1b3d6
Revises: d1f3a7c9e5b2
Create Date: 2026-07-16 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7e4c2f1b3d6'
down_revision = 'd1f3a7c9e5b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sync_state', sa.Column('last_success_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('sync_state', 'last_success_at')
