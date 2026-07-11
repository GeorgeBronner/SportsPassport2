"""College football adapter — CollegeFootballData.com (CFBD).

Ported from the original SportsPassport2 CollegeFootballDataService and
adapted to the multi-league schema. CFBD is both the historical and the
ongoing source for CFB (1990+), authenticated with an optional API key.
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, Optional

import httpx

from sports_passport.core.config import settings
from sports_passport.models.team import Team
from sports_passport.services.adapters.base import LeagueAdapter, ImportResult
from sports_passport.services.importer import get_league, upsert_team, upsert_venue, upsert_game

logger = logging.getLogger(__name__)


class CfbAdapter(LeagueAdapter):
    league_code = "CFB"
    source = "cfbd"

    def __init__(self, db):
        super().__init__(db)
        self.base_url = settings.cfb_api_url
        self.headers = {}
        if settings.cfb_api_key:
            self.headers["Authorization"] = f"Bearer {settings.cfb_api_key}"

    async def _get(self, endpoint: str, params: Dict[str, Any] = None) -> Any:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    def _upsert_team_row(self, league_id: int, team_data: dict, default_classification: str) -> bool:
        _, created = upsert_team(
            self.db,
            source=self.source,
            source_team_id=str(team_data.get("id")),
            league_id=league_id,
            name=team_data.get("school"),
            nickname=team_data.get("mascot"),
            abbreviation=team_data.get("abbreviation"),
            conference=team_data.get("conference"),
            division=team_data.get("division"),
            classification=team_data.get("classification", default_classification),
        )
        return created

    async def import_teams(self) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)

        fbs_teams = await self._get("/teams/fbs")
        seen = set()
        for team_data in fbs_teams:
            if team_data.get("id") in seen:
                continue
            seen.add(team_data.get("id"))
            if self._upsert_team_row(league.id, team_data, "fbs"):
                result.teams_imported += 1

        # FCS teams are opponents in some FBS games; import is best-effort.
        try:
            fcs_teams = await self._get("/teams", params={"classification": "fcs"})
            for team_data in fcs_teams:
                if team_data.get("id") in seen:
                    continue
                seen.add(team_data.get("id"))
                if self._upsert_team_row(league.id, team_data, "fcs"):
                    result.teams_imported += 1
        except Exception as e:
            result.errors.append(f"FCS team import skipped: {e}")

        self.db.commit()
        return result

    async def import_venues(self) -> ImportResult:
        result = ImportResult(league=self.league_code)
        venues_data = await self._get("/venues")
        for venue_data in venues_data:
            _, created = upsert_venue(
                self.db,
                source=self.source,
                source_venue_id=str(venue_data.get("id")),
                name=venue_data.get("name"),
                city=venue_data.get("city"),
                state=venue_data.get("state"),
                country=venue_data.get("countryCode") or "USA",
                capacity=venue_data.get("capacity"),
            )
            if created:
                result.venues_imported += 1
        self.db.commit()
        return result

    async def import_season(self, season: int) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)

        games_data = await self._get("/games", params={
            "year": season,
            "seasonType": "both",
            "division": "fbs",
        })

        # Team/venue lookups by source id, resolved once per season
        teams_by_name = {
            t.name: t.id
            for t in self.db.query(Team).filter(Team.league_id == league.id).all()
        }
        from sports_passport.models.venue import Venue
        venues_by_source = {
            v.source_venue_id: v.id
            for v in self.db.query(Venue).filter(Venue.source == self.source).all()
        }

        for game_data in games_data:
            home_id = teams_by_name.get(game_data.get("homeTeam"))
            away_id = teams_by_name.get(game_data.get("awayTeam"))
            if not home_id or not away_id:
                continue  # non-FBS/FCS opponent we don't track

            start_date = self._parse_date(game_data.get("startDate"))
            if not start_date:
                continue

            venue_id = None
            if game_data.get("venueId") is not None:
                venue_id = venues_by_source.get(str(game_data.get("venueId")))

            _, created = upsert_game(
                self.db,
                source=self.source,
                source_game_id=str(game_data.get("id")),
                league_id=league.id,
                home_team_id=home_id,
                away_team_id=away_id,
                home_score=game_data.get("homePoints"),
                away_score=game_data.get("awayPoints"),
                start_date=start_date,
                has_time=True,
                season=season,
                season_type=game_data.get("seasonType"),
                week=game_data.get("week"),
                venue_id=venue_id,
                neutral_site=bool(game_data.get("neutralSite")),
                attendance=game_data.get("attendance"),
            )
            if created:
                result.games_imported += 1
            else:
                result.games_updated += 1

        self.db.commit()
        return result

    async def import_historical(self, start_season: int, end_season: int) -> ImportResult:
        result = ImportResult(league=self.league_code)
        result.merge(await self.import_teams())
        result.merge(await self.import_venues())
        for season in range(start_season, end_season + 1):
            logger.info("CFB import: season %s", season)
            result.merge(await self.import_season(season))
        return result

    async def sync_recent(self, since: date) -> ImportResult:
        # CFB seasons span Aug–Jan; Jan/Feb dates belong to the prior season.
        season = since.year - 1 if since.month < 6 else since.year
        return await self.import_season(season)

    @staticmethod
    def _parse_date(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
