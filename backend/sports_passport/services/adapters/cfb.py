"""College football adapter — CollegeFootballData.com (CFBD).

Ported from the original SportsPassport2 CollegeFootballDataService and
adapted to the multi-league schema. CFBD is both the historical and the
ongoing source for CFB (1990+), authenticated with an optional API key.
"""
import logging
from datetime import date, datetime
from typing import Any

from sports_passport.core.config import settings
from sports_passport.models.team import Team
from sports_passport.services.adapters import local_time, venue_seed
from sports_passport.services.adapters.base import ImportResult, LeagueAdapter
from sports_passport.services.importer import get_league, upsert_game, upsert_team, upsert_venue

logger = logging.getLogger(__name__)


class CfbAdapter(LeagueAdapter):
    league_code = "CFB"
    source = "cfbd"
    # CFBD has no date filter on /games, so the nightly sync pulls a whole
    # season. On a college football Saturday night that response has hit the
    # 30s default (two Sentry ReadTimeouts, both at the 01:00 run).
    http_timeout_seconds = 60.0

    def __init__(self, db):
        super().__init__(db)
        self.base_url = settings.cfb_api_url
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

    def _upsert_team_row(
        self, league_id: int, team_data: dict, default_classification: str
    ) -> bool:
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
            # `or`, not dict.get's default: CFBD returns the key with a null
            # value (not a missing key) for a team it hasn't classified.
            classification=team_data.get("classification") or default_classification,
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

        # Every other school — FCS opponents, and the occasional Division II/III
        # or NAIA "money game" opponent CFBD's /games still reports — from one
        # unfiltered /teams pull, best-effort. /teams has no classification
        # filter (CFBD silently ignores one, same as `division` on /games), so
        # each row keeps CFBD's own classification; the 1,200-odd it hasn't
        # classified get "other". Without these, import_season's unmatched-
        # team check would permanently wedge on an opponent we never asked
        # for. See docs/open_issues.md #14 and #16.
        try:
            all_teams = await self._get("/teams")
            for team_data in all_teams:
                if team_data.get("id") in seen:
                    continue
                seen.add(team_data.get("id"))
                if self._upsert_team_row(league.id, team_data, "other"):
                    result.teams_imported += 1
        except Exception as e:
            result.errors.append(f"non-FBS team import skipped: {e}")

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
                # CFBD misspells a couple of cities (open_issues.md #11).
                city=venue_seed.correct_city(venue_data.get("city"), venue_data.get("state")),
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
            # `classification`, never `division`: CFBD silently ignores an
            # unknown parameter, and `division` returned every NCAA division
            # (~3,900 games a season instead of ~950) from the scaffold on.
            # Means "at least one FBS team", so FBS-vs-FCS games stay in.
            "classification": "fbs",
        })

        # Team/venue lookups by source id, resolved once per season. Keyed on
        # source_team_id, not name: team names are reused/renamed over time,
        # so a name key can silently misfile or drop games (see nfl.py's
        # _team_lookup docstring for the same reasoning).
        teams_by_source = {
            t.source_team_id: t.id
            for t in self.db.query(Team).filter(Team.league_id == league.id).all()
            if t.source_team_id
        }
        from sports_passport.models.venue import Venue
        venues_by_source = {
            v.source_venue_id: v.id
            for v in self.db.query(Venue).filter(Venue.source == self.source).all()
        }

        for game_data in games_data:
            home_id = teams_by_source.get(str(game_data.get("homeId")))
            away_id = teams_by_source.get(str(game_data.get("awayId")))
            if not home_id or not away_id:
                # Most misses are a non-FBS/FCS opponent we don't track, but
                # a renamed/reclassified team would look identical, so record
                # it rather than dropping the game with no signal.
                result.errors.append(
                    f"game {game_data.get('id')}: unmatched team "
                    f"{game_data.get('awayTeam')} @ {game_data.get('homeTeam')}"
                )
                continue

            start_date = self._parse_date(game_data.get("startDate"))
            if not start_date:
                continue
            # An unscheduled kickoff comes as a midnight-Eastern placeholder,
            # not a real time. Park it date-only on its Eastern game day, the
            # way cbb.py treats startTimeTbd.
            has_time = not game_data.get("startTimeTBD", False)
            if not has_time:
                start_date = local_time.date_only(local_time.utc_to_eastern(start_date))

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
                has_time=has_time,
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
        # CFBD's /games only filters by year + seasonType, never by date, so
        # "recent" means re-upserting whole seasons (~950 games each). The
        # upserts are idempotent, so this is wasteful rather than wrong. A
        # window spanning a season boundary (since in one season, today in
        # the next) must still cover both — a single season() call would
        # silently miss whichever end since didn't land in.
        #
        # Refresh the team roster first, every run: a newly-scheduled money
        # game against a school CFBD hadn't returned before (see
        # docs/open_issues.md #14) would otherwise unmatched-team-error every
        # night until the next historical/admin re-import happened to catch
        # it. import_teams is a handful of idempotent upserts, cheap next to
        # the season pulls below.
        result = ImportResult(league=self.league_code)
        result.merge(await self.import_teams())

        first_season = self._season_of(since)
        last_season = self._season_of(date.today())
        for season in range(first_season, last_season + 1):
            logger.info(
                "CFB sync since %s: no date filter on CFBD /games, re-syncing all of season %s",
                since, season,
            )
            result.merge(await self.import_season(season))
        return result

    @staticmethod
    def _season_of(d: date) -> int:
        # CFB seasons span Aug–Jan; Jan/Feb dates belong to the prior season.
        return d.year - 1 if d.month < 6 else d.year

    @staticmethod
    def _parse_date(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
