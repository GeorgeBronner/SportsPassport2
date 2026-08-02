"""College basketball adapter — CollegeBasketballData.com (CBBD).

CBBD is CFBD's sister project (same maintainer, same free-key Bearer-token
auth model) — confirmed live 2026-07-12 that the existing CFB_API_KEY works
unmodified as a CBBD token, so this adapter reuses settings.cfb_api_key
directly rather than adding a separate key setting.

Scope is Division I men's basketball (the app's trackable floor, same idea
as CFB's FBS-only floor), with a 1990 historical floor matching CFB's — not
a data-availability limit (live testing found clean CBBD game data back to
at least 1950), a scope choice to bound decades of conference-realignment
bookkeeping. See docs/SP3_data_sources.md's CBB section for the full research and
docs/SP3_plan.md for the floor-year decision.

Non-D-I opponents ("buy games"): D-I teams occasionally play D-II/D-III/NAIA
opponents, and those games should still be loggable. CBBD's `/games` payload
gives both teams' numeric IDs and names regardless of division, and its full
`/teams` registry (no `season` filter) has a real row — school/mascot/
abbreviation — for non-D-I opponents too, just without conference/venue/
location. No manual seed lookup needed (confirmed live against a real IU
Indianapolis vs. Spalding/NAIA game).

Classification: CBBD's `/teams?season=X` returns that season's D-I-only
roster (confirmed: every row has a non-null conference), which is the one
reliable "is this team D-I" signal available outside game data — used by
`import_teams`. During historical/sync game processing, a newly-encountered
team's classification is instead read straight off that game's own
home/awayConference field (non-null -> "d1", null -> "non-d1"), avoiding an
extra per-season roster call; like CFB's fbs/fcs, this is a single label per
team row, not season-tracked.

Pagination: GET /games caps at exactly 3000 rows regardless of season/
seasonType filters (verified live — a full season's regular-season games
exceeds this before the season ends). The real pagination mechanism is
startDateRange/endDateRange; this adapter chunks every season into 6 monthly
windows (Nov-Apr), verified safely under the cap even in the highest-volume
month (November) and the tournament-heavy month (March).
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any

from sports_passport.core.config import settings
from sports_passport.models.team import Team
from sports_passport.services.adapters import local_time
from sports_passport.services.adapters.base import ImportResult, LeagueAdapter
from sports_passport.services.importer import get_league, upsert_game, upsert_team, upsert_venue

logger = logging.getLogger(__name__)

SEASON_TYPES = ("regular", "postseason")


class CbbAdapter(LeagueAdapter):
    league_code = "CBB"
    source = "cbbd"

    def __init__(self, db):
        super().__init__(db)
        self.base_url = settings.cbb_api_url
        self.headers = {}
        if settings.cfb_api_key:
            self.headers["Authorization"] = f"Bearer {settings.cfb_api_key}"

    async def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        response = await self.http.get(
            f"{self.base_url}{endpoint}",
            headers=self.headers,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _current_cbbd_season() -> int:
        """CBBD's `season` is the end calendar year (season=2024 -> 2023-24).
        Jan-Apr belongs to the season ending that spring; May-Dec belongs to
        the season starting/ending the following spring."""
        today = date.today()
        return today.year if today.month <= 4 else today.year + 1

    @staticmethod
    def _month_chunks(our_season: int) -> list[tuple[str, str]]:
        """(startDateRange, endDateRange) pairs covering Nov(our_season)
        through Apr(our_season+1), one per calendar month."""
        months = [
            (11, our_season), (12, our_season),
            (1, our_season + 1), (2, our_season + 1),
            (3, our_season + 1), (4, our_season + 1),
        ]
        chunks = []
        for month, year in months:
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            chunks.append((start.isoformat(), end.isoformat()))
        return chunks

    def _upsert_team_row(self, league_id: int, row: dict, classification: str) -> bool:
        _, created = upsert_team(
            self.db,
            source=self.source,
            source_team_id=str(row.get("id")),
            league_id=league_id,
            name=row.get("school"),
            nickname=row.get("mascot"),
            abbreviation=row.get("abbreviation"),
            city=row.get("currentCity"),
            state=row.get("currentState"),
            conference=row.get("conference"),
            classification=classification,
        )
        return created

    async def import_teams(self) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)

        rows = await self._get("/teams", params={"season": self._current_cbbd_season()})
        for row in rows:
            if self._upsert_team_row(league.id, row, "d1"):
                result.teams_imported += 1

        self.db.commit()
        return result

    def _team_lookup(self, league_id: int) -> dict[str, int]:
        teams = self.db.query(Team).filter(Team.league_id == league_id).all()
        return {t.source_team_id: t.id for t in teams if t.source_team_id}

    def _resolve_team(
        self, league_id: int, source_id: int | None, conference: str | None,
        registry_by_id: dict, by_source_id: dict, result: ImportResult,
    ) -> int | None:
        if source_id is None:
            return None
        key = str(source_id)
        team_id = by_source_id.get(key)
        if team_id is not None:
            return team_id

        row = registry_by_id.get(key)
        if row is None:
            return None

        classification = "d1" if conference else "non-d1"
        team, created = upsert_team(
            self.db,
            source=self.source,
            source_team_id=key,
            league_id=league_id,
            name=row.get("school"),
            nickname=row.get("mascot"),
            abbreviation=row.get("abbreviation"),
            city=row.get("currentCity"),
            state=row.get("currentState"),
            conference=row.get("conference"),
            classification=classification,
        )
        if created:
            result.teams_imported += 1
        by_source_id[key] = team.id
        return team.id

    def _upsert_game_row(
        self, league_id: int, row: dict, registry_by_id: dict, by_source_id: dict,
        venue_cache: dict, result: ImportResult,
    ) -> None:
        if row.get("status") != "final":
            return

        season_type = row.get("seasonType")
        if season_type not in SEASON_TYPES:
            result.errors.append(f"game {row.get('id')}: unknown seasonType {season_type!r}")
            return

        home_id = self._resolve_team(
            league_id,
            row.get("homeTeamId"),
            row.get("homeConference"),
            registry_by_id,
            by_source_id,
            result,
        )
        away_id = self._resolve_team(
            league_id,
            row.get("awayTeamId"),
            row.get("awayConference"),
            registry_by_id,
            by_source_id,
            result,
        )
        if home_id is None or away_id is None:
            result.errors.append(f"game {row.get('id')}: unmatched team")
            return

        start_date = self._parse_date(row.get("startDate"))
        if not start_date:
            result.errors.append(f"game {row.get('id')}: bad date {row.get('startDate')!r}")
            return

        # startTimeTbd rows carry a CBBD placeholder rather than a real tip-off
        # (a noon-ET one, in practice), so park them date-only on the same
        # calendar day they already display on.
        has_time = not row.get("startTimeTbd", False)
        if not has_time:
            start_date = local_time.date_only(start_date)

        venue_id = None
        venue_name = row.get("venue")
        if row.get("venueId") is not None and venue_name:
            source_venue_id = str(row["venueId"])
            venue_id = venue_cache.get(source_venue_id)
            if venue_id is None:
                venue, created = upsert_venue(
                    self.db,
                    source=self.source,
                    source_venue_id=source_venue_id,
                    name=venue_name,
                    city=row.get("city"),
                    state=row.get("state"),
                    country="USA",
                )
                venue_id = venue.id
                venue_cache[source_venue_id] = venue_id
                if created:
                    result.venues_imported += 1

        _, created = upsert_game(
            self.db,
            source=self.source,
            source_game_id=str(row["id"]),
            league_id=league_id,
            home_team_id=home_id,
            away_team_id=away_id,
            home_score=row.get("homePoints"),
            away_score=row.get("awayPoints"),
            start_date=start_date,
            has_time=has_time,
            season=row["season"] - 1,
            season_type=season_type,
            venue_id=venue_id,
            neutral_site=bool(row.get("neutralSite")),
            attendance=row.get("attendance") or None,  # CBBD sends 0 for unknown
        )
        if created:
            result.games_imported += 1
        else:
            result.games_updated += 1

    async def _load_registry(self) -> dict:
        rows = await self._get("/teams")
        return {str(r.get("id")): r for r in rows}

    async def import_historical(self, start_season: int, end_season: int) -> ImportResult:
        result = ImportResult(league=self.league_code)
        result.merge(await self.import_teams())

        league = get_league(self.db, self.league_code)
        registry_by_id = await self._load_registry()
        by_source_id = self._team_lookup(league.id)
        venue_cache: dict[str, int] = {}

        for season in range(start_season, end_season + 1):
            logger.info("CBB import: season %s", season)
            for start, end in self._month_chunks(season):
                rows = await self._get(
                    "/games", params={"startDateRange": start, "endDateRange": end}
                )
                for row in rows:
                    self._upsert_game_row(
                        league.id, row, registry_by_id, by_source_id, venue_cache, result
                    )
            self.db.commit()

        return result

    async def sync_recent(self, since: date) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)
        registry_by_id = await self._load_registry()
        by_source_id = self._team_lookup(league.id)
        venue_cache: dict[str, int] = {}

        rows = await self._get("/games", params={
            "startDateRange": since.isoformat(),
            "endDateRange": (date.today() + timedelta(days=1)).isoformat(),
        })
        for row in rows:
            self._upsert_game_row(league.id, row, registry_by_id, by_source_id, venue_cache, result)

        self.db.commit()
        return result

    @staticmethod
    def _parse_date(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
