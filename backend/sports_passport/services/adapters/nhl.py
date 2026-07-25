"""NHL adapter — official NHL API (api-web.nhle.com / api.nhle.com).

Free, keyless, and official; covers both the historical backfill and ongoing
sync (single-source league). Endpoints verified live:

- Teams (all-time, incl. defunct, with franchiseId):
    https://api.nhle.com/stats/rest/en/team
- Season schedule per club (goes back to 1917):
    https://api-web.nhle.com/v1/club-schedule-season/{TRICODE}/{SEASONID}
- Standings on a date (which teams played that season):
    https://api-web.nhle.com/v1/standings/{YYYY-MM-DD}
- Scores by date (sync):
    https://api-web.nhle.com/v1/score/{YYYY-MM-DD}

`season` is stored as the start year (1993 = the 1993-94 season); the API's
seasonId is f"{year}{year+1}". gameType: 1=preseason, 2=regular, 3=postseason.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sports_passport.core.config import settings
from sports_passport.models.team import Team
from sports_passport.services.adapters.base import LeagueAdapter, ImportResult
from sports_passport.services.importer import get_league, upsert_team, upsert_venue, upsert_game

logger = logging.getLogger(__name__)

TEAMS_URL = "https://api.nhle.com/stats/rest/en/team"
GAME_TYPES = {1: "preseason", 2: "regular", 3: "postseason"}
# Be polite to the free API during the big one-time backfill
BACKFILL_DELAY_SECONDS = 0.25


class NhlAdapter(LeagueAdapter):
    league_code = "NHL"
    source = "nhl"

    async def _get(self, url: str, ok_404: bool = False) -> Optional[Any]:
        response = await self.http.get(url)
        if ok_404 and response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def import_teams(self) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)

        data = await self._get(TEAMS_URL)
        for row in data["data"]:
            _, created = upsert_team(
                self.db,
                source=self.source,
                source_team_id=str(row["id"]),
                league_id=league.id,
                name=row.get("fullName"),
                abbreviation=row.get("triCode"),
                franchise_id=row.get("franchiseId"),
            )
            if created:
                result.teams_imported += 1
        self.db.commit()
        return result

    def _team_lookups(self, league_id: int) -> tuple[dict, dict]:
        """(by numeric source id, by abbreviation) for this league's teams."""
        teams = self.db.query(Team).filter(Team.league_id == league_id).all()
        by_source_id = {t.source_team_id: t.id for t in teams}
        by_abbrev = {t.abbreviation: t.id for t in teams if t.abbreviation}
        return by_source_id, by_abbrev

    def _resolve_team(self, payload: dict, by_source_id: dict, by_abbrev: dict) -> Optional[int]:
        team_id = by_source_id.get(str(payload.get("id")))
        if team_id is None:
            team_id = by_abbrev.get(payload.get("abbrev"))
        return team_id

    def _upsert_api_game(self, league_id: int, game: dict,
                         by_source_id: dict, by_abbrev: dict,
                         result: ImportResult) -> None:
        game_type = game.get("gameType")
        if game_type not in (2, 3):  # regular + postseason only
            return

        home_id = self._resolve_team(game.get("homeTeam", {}), by_source_id, by_abbrev)
        away_id = self._resolve_team(game.get("awayTeam", {}), by_source_id, by_abbrev)
        if home_id is None or away_id is None:
            result.errors.append(
                f"game {game.get('id')}: unmatched team "
                f"{game.get('awayTeam', {}).get('abbrev')} @ {game.get('homeTeam', {}).get('abbrev')}"
            )
            return

        start_date, has_time = self._parse_start(game)
        if start_date is None:
            result.errors.append(f"game {game.get('id')}: no date")
            return

        venue_id = None
        venue_name = (game.get("venue") or {}).get("default")
        if venue_name:
            venue, created = upsert_venue(
                self.db,
                source=self.source,
                source_venue_id=venue_name,  # API exposes no venue id; name is the key
                name=venue_name,
            )
            venue_id = venue.id
            if created:
                result.venues_imported += 1

        last_period = (game.get("gameOutcome") or {}).get("lastPeriodType")
        overtime_flag = last_period if last_period and last_period != "REG" else None

        season_raw = game.get("season")  # e.g. 19931994
        season = int(str(season_raw)[:4]) if season_raw else start_date.year

        _, created = upsert_game(
            self.db,
            source=self.source,
            source_game_id=str(game["id"]),
            league_id=league_id,
            home_team_id=home_id,
            away_team_id=away_id,
            home_score=game.get("homeTeam", {}).get("score"),
            away_score=game.get("awayTeam", {}).get("score"),
            start_date=start_date,
            has_time=has_time,
            season=season,
            season_type=GAME_TYPES[game_type],
            venue_id=venue_id,
            overtime_flag=overtime_flag,
            neutral_site=bool(game.get("neutralSite")),
        )
        if created:
            result.games_imported += 1
        else:
            result.games_updated += 1

    async def _season_tricodes(self, season_start_year: int) -> list[str]:
        """Abbreviations of teams in the standings for a season (empty if no season, e.g. 2004-05)."""
        standings = await self._get(
            f"{settings.nhl_api_url}/standings/{season_start_year + 1}-04-01", ok_404=True
        )
        if not standings:
            return []
        return sorted({row["teamAbbrev"]["default"] for row in standings.get("standings", [])})

    async def import_season(self, season_start_year: int) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)
        by_source_id, by_abbrev = self._team_lookups(league.id)

        season_id = f"{season_start_year}{season_start_year + 1}"
        seen_game_ids: set[str] = set()

        tricodes = await self._season_tricodes(season_start_year)
        if not tricodes:
            result.errors.append(f"season {season_start_year}: no standings (lockout or bad year?)")
            return result

        for tricode in tricodes:
            payload = await self._get(
                f"{settings.nhl_api_url}/club-schedule-season/{tricode}/{season_id}", ok_404=True
            )
            await asyncio.sleep(BACKFILL_DELAY_SECONDS)
            if not payload:
                continue
            for game in payload.get("games", []):
                gid = str(game.get("id"))
                if gid in seen_game_ids:  # every game appears in both clubs' schedules
                    continue
                seen_game_ids.add(gid)
                self._upsert_api_game(league.id, game, by_source_id, by_abbrev, result)

        self.db.commit()
        logger.info("NHL season %s: %s games imported, %s updated",
                    season_start_year, result.games_imported, result.games_updated)
        return result

    async def import_historical(self, start_season: int, end_season: int) -> ImportResult:
        result = ImportResult(league=self.league_code)
        result.merge(await self.import_teams())
        for season in range(start_season, end_season + 1):
            result.merge(await self.import_season(season))
        return result

    async def sync_recent(self, since: date) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)
        by_source_id, by_abbrev = self._team_lookups(league.id)

        day = since
        today = date.today()
        while day <= today:
            payload = await self._get(f"{settings.nhl_api_url}/score/{day.isoformat()}", ok_404=True)
            if payload:
                for game in payload.get("games", []):
                    # /score/{date} includes surrounding days; only take the target date
                    if game.get("gameDate") != day.isoformat():
                        continue
                    self._upsert_api_game(league.id, game, by_source_id, by_abbrev, result)
            day += timedelta(days=1)

        self.db.commit()
        return result

    @staticmethod
    def _parse_start(game: dict) -> tuple[Optional[datetime], bool]:
        raw_utc = game.get("startTimeUTC")
        if raw_utc:
            try:
                return datetime.fromisoformat(raw_utc.replace("Z", "+00:00")).replace(tzinfo=None), True
            except ValueError:
                pass
        raw_date = game.get("gameDate")
        if raw_date:
            try:
                return datetime.fromisoformat(raw_date), False
            except ValueError:
                pass
        return None, False
