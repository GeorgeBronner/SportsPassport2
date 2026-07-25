from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, true
from sqlalchemy.orm import relationship
from sports_passport.db.database import Base


class SyncState(Base):
    """Per-league nightly-sync configuration and last-run record.

    One row per league (created lazily the first time the scheduler or the
    admin UI touches a league). `enabled` gates the nightly job; the rest is
    the outcome of the most recent run, surfaced in the admin status table.
    """
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), unique=True, nullable=False, index=True)
    # server_default mirrors migration d1f3a7c9e5b2, which every existing
    # database was built from. Without it here, create_all() emits a table
    # without the DEFAULT and --autogenerate reports a phantom change.
    enabled = Column(Boolean, default=True, server_default=true(), nullable=False)

    last_run_at = Column(DateTime, nullable=True)          # naive UTC, like game start_date — most recent attempt
    last_success_at = Column(DateTime, nullable=True)      # most recent successful run; drives the adaptive lookback
    last_status = Column(String, nullable=True)            # 'success' | 'error' | 'running'
    last_games_imported = Column(Integer, nullable=True)
    last_games_updated = Column(Integer, nullable=True)
    last_error = Column(String, nullable=True)             # first error line, if any
    last_duration_ms = Column(Integer, nullable=True)

    league = relationship("League")
