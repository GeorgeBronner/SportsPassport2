"""normalize bulk-imported NBA and NFL start_date to UTC

Revision ID: c4d8e2a1f7b3
Revises: f3a9d4b6c281
Create Date: 2026-08-01 10:00:00.000000

`games.start_date` is defined as UTC (SP3_plan.md §3) and the API stamps an
explicit UTC offset on it, but two bulk paths wrote naive US Eastern wall
clocks into the same column (docs/SP3_open_issues.md #7): nflverse's
`gametime` and the NBA Kaggle `Games.csv` `gameDate`. Both publish Eastern
for every game regardless of where it is played, so both shift by the
Eastern offset in effect on that date.

The NBA rows also claimed `has_time=True` back to 1969, but the CSV has no
real tip-offs before the 1996 season — every earlier season carries one or
two placeholder clock values for the whole year. Those rows are set to
has_time=False at naive midnight so the UI stops implying a time the source
never had (has_time=False renders pinned to UTC, so midnight keeps the
correct calendar day).

Not reversible: the pre-1996 placeholder clock values are discarded, so
downgrade raises rather than pretending to restore them.

ESPN-inserted NBA rows (`source_game_id LIKE 'espn-%'`) already hold true UTC
and are excluded. A Kaggle-keyed row that an ESPN sync had already rewritten
to UTC would be indistinguishable and would double-shift; no such row exists,
because the ESPN sync path has never completed a run against this schema.
"""
from alembic import op
import sqlalchemy as sa

from sports_passport.services.adapters.local_time import eastern_to_utc

# revision identifiers, used by Alembic.
revision = 'c4d8e2a1f7b3'
down_revision = 'f3a9d4b6c281'
branch_labels = None
depends_on = None

FIRST_NBA_SEASON_WITH_REAL_TIMES = 1996


def _apply(bind, updates) -> None:
    """updates: [(start_date, has_time, id), ...]"""
    for chunk_start in range(0, len(updates), 1000):
        bind.execute(
            sa.text("UPDATE games SET start_date = :start, has_time = :ht WHERE id = :id"),
            [
                {"start": s, "ht": h, "id": i}
                for s, h, i in updates[chunk_start:chunk_start + 1000]
            ],
        )


def upgrade() -> None:
    bind = op.get_bind()

    # --- NBA: US Eastern -> UTC, and drop the pre-1996 placeholder times ---
    nba_rows = bind.execute(
        sa.text(
            """
            SELECT id, start_date, season FROM games
            WHERE source = 'nba-kaggle'
              AND source_game_id NOT LIKE 'espn-%'
              AND start_date IS NOT NULL
            """
        )
    ).fetchall()

    nba_updates = []
    for row_id, start, season in nba_rows:
        start = _as_datetime(start)
        if start is None:
            continue
        if season is not None and season < FIRST_NBA_SEASON_WITH_REAL_TIMES:
            nba_updates.append((start.replace(hour=0, minute=0, second=0, microsecond=0), False, row_id))
        else:
            nba_updates.append((eastern_to_utc(start), True, row_id))
    _apply(bind, nba_updates)

    # --- NFL: US Eastern -> UTC (date-only rows have no time to shift) ---
    nfl_rows = bind.execute(
        sa.text(
            """
            SELECT id, start_date FROM games
            WHERE source = 'nflverse' AND has_time = 1 AND start_date IS NOT NULL
            """
        )
    ).fetchall()

    nfl_updates = []
    for row_id, start in nfl_rows:
        start = _as_datetime(start)
        if start is not None:
            nfl_updates.append((eastern_to_utc(start), True, row_id))
    _apply(bind, nfl_updates)


def _as_datetime(value):
    """SQLite hands back a str or a datetime depending on the driver path."""
    from datetime import datetime

    if value is None or isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def downgrade() -> None:
    raise NotImplementedError(
        "Irreversible: the pre-1996 NBA placeholder tip-off times this migration "
        "replaced with midnight are not recoverable from the database. Restore "
        "from a backup taken before the upgrade."
    )
