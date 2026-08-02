"""LeagueAdapter interface — one implementation per league.

Contract (see docs/SP3_plan.md §4):
- import_teams: load/refresh the league's teams.
- import_historical: one-time bulk backfill from local files or API pagination.
- sync_recent: cheap incremental update hitting only free APIs; run by the
  nightly scheduler and the admin sync endpoint.

All methods are idempotent upserts keyed on (source, source_*_id).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import httpx
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

    # Passed to the shared httpx client; adapters override for per-source needs
    # (redirect following, anti-bot headers).
    http_client_kwargs: dict = {}
    http_timeout_seconds: float = 30.0

    def __init__(self, db: Session):
        self.db = db
        self._http: httpx.AsyncClient | None = None

    @property
    def http(self) -> httpx.AsyncClient:
        """Connection-pooled client shared by every request this adapter makes.

        A historical backfill is thousands of requests to one host; a client
        per request would pay a fresh TCP+TLS handshake for each. Created
        lazily so adapters that never touch the network (NBA reads a local
        CSV) don't open one, and so tests can patch `_get` without a client
        ever existing. Callers own the lifecycle via `aclose`.
        """
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=self.http_timeout_seconds, **self.http_client_kwargs
            )
        return self._http

    async def aclose(self) -> None:
        """Release pooled connections. Safe to call when none were opened."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @abstractmethod
    async def import_teams(self) -> ImportResult:
        ...

    @abstractmethod
    async def import_historical(self, start_season: int, end_season: int) -> ImportResult:
        ...

    @abstractmethod
    async def sync_recent(self, since: date) -> ImportResult:
        ...
