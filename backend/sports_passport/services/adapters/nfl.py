"""NFL adapter — nflverse (github.com/nflverse/nfldata).

Free, keyless, community-maintained; a single source covers both historical
backfill and ongoing sync, since nflverse's `games.csv` already carries the
full schedule (1999-present, auto-updated, including the in-progress
season). Per a 2026-07-11 decision, NFL ships with a **1999 floor** rather
than the plan's original 1970 target: the 1970-1998 gap would need the
Kaggle "Spreadspoke" CSV, which now sits behind a Kaggle login or a paid
tier (see docs/SP3_data_sources.md) — deferred rather than blocking on that.

- Games (1999-present):
    https://github.com/nflverse/nfldata/raw/master/data/games.csv
- Team metadata (2002-present; abbreviations are stable back to 1999):
    https://github.com/nflverse/nfldata/raw/master/data/teams.csv

`nfl_team_id` from teams.csv is stable across relocations (e.g. STL/LA
Rams both carry 2510) and is stored as our `franchise_id`; the abbreviation
itself is the per-era team identity (STL and LA Rams are separate team
rows), matching the CFB/NHL pattern. `gametime` in the source data is US
Eastern local time for every game regardless of where it is played, so
`_parse_start` converts it to UTC — `games.start_date` is defined as UTC
(SP3_plan.md §3) and the API serializer stamps an explicit UTC offset on
it, so storing Eastern here would publish a time 4-5 hours off.
"""
import csv
import io
import logging
from datetime import date, datetime
from typing import Optional

from sports_passport.models.team import Team
from sports_passport.services.adapters import local_time, venue_seed
from sports_passport.services.adapters.base import LeagueAdapter, ImportResult
from sports_passport.services.importer import get_league, upsert_team, upsert_venue, upsert_game

logger = logging.getLogger(__name__)

GAMES_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
TEAMS_URL = "https://github.com/nflverse/nfldata/raw/master/data/teams.csv"
GAME_TYPES = {"REG": "regular", "WC": "postseason", "DIV": "postseason", "CON": "postseason", "SB": "postseason"}


class NflAdapter(LeagueAdapter):
    league_code = "NFL"
    source = "nflverse"

    http_client_kwargs = {"follow_redirects": True}

    async def _get_csv(self, url: str) -> list[dict]:
        response = await self.http.get(url)
        response.raise_for_status()
        return list(csv.DictReader(io.StringIO(response.text)))

    async def import_teams(self) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)

        games = await self._get_csv(GAMES_URL)
        team_meta = {row["team"]: row for row in await self._get_csv(TEAMS_URL)}

        seasons_by_abbrev: dict[str, list[int]] = {}
        for row in games:
            season = int(row["season"])
            for abbrev in (row["home_team"], row["away_team"]):
                seasons_by_abbrev.setdefault(abbrev, []).append(season)
        current_season = max(int(row["season"]) for row in games)

        for abbrev, seasons in seasons_by_abbrev.items():
            meta = team_meta.get(abbrev, {})
            franchise_id = int(meta["nfl_team_id"]) if meta.get("nfl_team_id") else None
            last_season = max(seasons)
            _, created = upsert_team(
                self.db,
                source=self.source,
                source_team_id=abbrev,
                league_id=league.id,
                name=meta.get("full") or abbrev,
                nickname=meta.get("nickname"),
                abbreviation=abbrev,
                franchise_id=franchise_id,
                first_season=min(seasons),
                last_season=None if last_season == current_season else last_season,
            )
            if created:
                result.teams_imported += 1

        self.db.commit()
        return result

    def _team_lookup(self, league_id: int) -> dict[str, int]:
        teams = self.db.query(Team).filter(Team.league_id == league_id).all()
        return {t.abbreviation: t.id for t in teams if t.abbreviation}

    def _upsert_row(self, league_id: int, row: dict, by_abbrev: dict, result: ImportResult) -> None:
        home_id = by_abbrev.get(row["home_team"])
        away_id = by_abbrev.get(row["away_team"])
        if home_id is None or away_id is None:
            result.errors.append(
                f"game {row['game_id']}: unmatched team {row['away_team']} @ {row['home_team']}"
            )
            return

        start_date = self._parse_start(row)
        if start_date is None:
            result.errors.append(f"game {row['game_id']}: bad date {row.get('gameday')!r}")
            return

        venue_id = None
        stadium_id = row.get("stadium_id")
        if stadium_id:
            seed = venue_seed.nfl_stadiums().get(stadium_id)
            venue, created = upsert_venue(
                self.db,
                source=self.source,
                source_venue_id=stadium_id,
                name=row.get("stadium") or stadium_id,
                **(venue_seed.venue_fields(seed) if seed else {}),
            )
            venue_id = venue.id
            if created:
                result.venues_imported += 1

        _, created = upsert_game(
            self.db,
            source=self.source,
            source_game_id=row["game_id"],
            league_id=league_id,
            home_team_id=home_id,
            away_team_id=away_id,
            home_score=int(row["home_score"]) if row.get("home_score") else None,
            away_score=int(row["away_score"]) if row.get("away_score") else None,
            start_date=start_date,
            has_time=bool(row.get("gametime")),
            season=int(row["season"]),
            season_type=GAME_TYPES.get(row["game_type"], "regular"),
            week=int(row["week"]) if row.get("week") else None,
            venue_id=venue_id,
            neutral_site=row.get("location") == "Neutral",
            overtime_flag="OT" if row.get("overtime") == "1" else None,
        )
        if created:
            result.games_imported += 1
        else:
            result.games_updated += 1

    async def _import_games(
        self, result: ImportResult, *,
        min_season: Optional[int] = None, max_season: Optional[int] = None,
        since: Optional[date] = None,
    ) -> None:
        league = get_league(self.db, self.league_code)
        by_abbrev = self._team_lookup(league.id)
        games = await self._get_csv(GAMES_URL)
        for row in games:
            season = int(row["season"])
            if min_season is not None and season < min_season:
                continue
            if max_season is not None and season > max_season:
                continue
            if since is not None:
                gameday = row.get("gameday")
                if not gameday or date.fromisoformat(gameday) < since:
                    continue
            self._upsert_row(league.id, row, by_abbrev, result)
        self.db.commit()
        logger.info("NFL import: %s games imported, %s updated", result.games_imported, result.games_updated)

    async def import_historical(self, start_season: int, end_season: int) -> ImportResult:
        result = ImportResult(league=self.league_code)
        result.merge(await self.import_teams())
        await self._import_games(result, min_season=start_season, max_season=end_season)
        return result

    async def sync_recent(self, since: date) -> ImportResult:
        result = ImportResult(league=self.league_code)
        await self._import_games(result, since=since)
        return result

    @staticmethod
    def _parse_start(row: dict) -> Optional[datetime]:
        gameday = row.get("gameday")
        if not gameday:
            return None
        gametime = row.get("gametime")
        try:
            if gametime:
                return local_time.eastern_to_utc(
                    datetime.fromisoformat(f"{gameday}T{gametime}:00")
                )
            # No kickoff time: the date itself is already the local game day,
            # and the row goes in with has_time=False, so it stays at naive
            # midnight rather than being shifted into the previous day.
            return datetime.fromisoformat(gameday)
        except ValueError:
            return None
