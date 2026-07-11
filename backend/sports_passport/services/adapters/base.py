"""LeagueAdapter interface — one implementation per league.

Contract (see SP3_plan.md §4):
- import_teams: load/refresh the league's teams.
- import_historical: one-time bulk backfill from local files or API pagination.
- sync_recent: cheap incremental update hitting only free APIs; run by the
  nightly scheduler and the admin sync endpoint.

All methods are idempotent upserts keyed on (source, source_*_id).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from sqlalchemy.orm import Session


@dataclass
class ImportResult:
    league: str
    teams_imported: int = 0
    venues_imported: int = 0
    games_imported: int = 0
    games_updated: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: "ImportResult") -> "ImportResult":
        self.teams_imported += other.teams_imported
        self.venues_imported += other.venues_imported
        self.games_imported += other.games_imported
        self.games_updated += other.games_updated
        self.errors.extend(other.errors)
        return self


class LeagueAdapter(ABC):
    league_code: str
    source: str  # value stored in games.source / teams.source

    def __init__(self, db: Session):
        self.db = db

    @abstractmethod
    async def import_teams(self) -> ImportResult:
        ...

    @abstractmethod
    async def import_historical(self, start_season: int, end_season: int) -> ImportResult:
        ...

    @abstractmethod
    async def sync_recent(self, since: date) -> ImportResult:
        ...
