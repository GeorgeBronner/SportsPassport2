"""park date-only games at noon instead of midnight

Revision ID: a9f2c7e4b8d1
Revises: c4d8e2a1f7b3
Create Date: 2026-08-01 16:00:00.000000

A has_time=False row carries a calendar game day and no real kickoff, so its
time-of-day is a storage detail — but midnight is the one choice that is only
correct by convention. It displays correctly solely because the frontend pins
has_time=False rows to UTC (utils/format.ts displayTimeZone); any consumer that
forgets that pin — a new component, a CSV export, a chart, a third-party reader
of the API — renders midnight UTC as the *previous* calendar day everywhere
west of Greenwich, which is the whole US.

Noon is right by construction instead: it lands on the correct calendar day for
every offset from UTC-11 through UTC+11.

This cannot change any displayed date. It only rewrites the time-of-day within
each row's existing UTC date, and has_time=False rows are rendered on that UTC
date. Verified against the live database before and after (see
docs/SP3_open_issues.md #8).

Reversible, with one wrinkle: 15 CBB rows sat at 17:00 rather than midnight —
CBBD noon-ET placeholders on startTimeTbd games — and downgrade returns every
row to midnight uniformly rather than restoring those. They were never real
tip-off times, which is why the rows are has_time=False in the first place.
"""
from alembic import op
import sqlalchemy as sa

from sports_passport.services.adapters.local_time import DATE_ONLY_HOUR

# revision identifiers, used by Alembic.
revision = 'a9f2c7e4b8d1'
down_revision = 'c4d8e2a1f7b3'
branch_labels = None
depends_on = None


def _set_hour(hour: int) -> None:
    """Move every date-only game to `hour` on the calendar day it already has.

    Done in SQL rather than row-by-row Python: this touches ~207k rows, and
    the whole point is that the date component is untouched, which
    strftime expresses directly.
    """
    op.get_bind().execute(
        sa.text(
            "UPDATE games "
            "SET start_date = strftime('%Y-%m-%d " + f"{hour:02d}" + ":00:00.000000', start_date) "
            "WHERE has_time = 0 AND start_date IS NOT NULL"
        )
    )


def upgrade() -> None:
    _set_hour(DATE_ONLY_HOUR)


def downgrade() -> None:
    _set_hour(0)
