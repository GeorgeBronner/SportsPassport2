from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sports_passport.db.database import Base

if TYPE_CHECKING:
    from sports_passport.models.league import League


class SyncState(Base):
    """Per-league nightly-sync configuration and last-run record.

    One row per league (created lazily the first time the scheduler or the
    admin UI touches a league). `enabled` gates the nightly job; the rest is
    the outcome of the most recent run, surfaced in the admin status table.
    """
    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    league_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leagues.id"), unique=True, index=True
    )
    # server_default mirrors migration d1f3a7c9e5b2, which every existing
    # database was built from. Without it here, create_all() emits a table
    # without the DEFAULT and --autogenerate reports a phantom change.
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    # naive UTC, like game start_date — most recent attempt
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    # most recent successful run; drives the adaptive lookback
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    # 'success' | 'error' | 'running'
    last_status: Mapped[str | None] = mapped_column(String)
    last_games_imported: Mapped[int | None] = mapped_column(Integer)
    last_games_updated: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(String)  # first error line, if any
    last_duration_ms: Mapped[int | None] = mapped_column(Integer)

    league: Mapped["League"] = relationship("League")
