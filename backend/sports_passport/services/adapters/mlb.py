"""MLB adapter — Retrosheet (retrosheet.org) game logs + park codes.

Free, keyless, official historical record; permissive license ("recipients
are free to make any use of the data, including commercial"). Like the
CFB/NHL/NFL adapters, games are fetched live from Retrosheet's static file
server rather than downloaded once into `data/raw/` — it's a plain static
host with no rate limit or ToS concern (see SP3_data_sources.md), so a
local copy buys nothing over re-fetching per import.

- Franchise/team directory (one row per team-identity era, franchise-linked
  via column 1, e.g. Montreal Expos + Washington Nationals both "WAS"):
    https://www.retrosheet.org/CurrentNames.csv
- Ballpark directory (park id -> name/city/state):
    https://www.retrosheet.org/parkcode.txt
- Season game logs (fixed-field CSV, no header, one row per game):
    https://www.retrosheet.org/gamelogs/gl{season}.zip

Compliance guardrail: Retrosheet is the bulk-backfill source. The MLB
Stats API (`sync_recent`) must never be used for bulk backfill per its
terms (SP3_data_sources.md) — only for small "since date" queries.

Scope note: Retrosheet's gamelogs cover **regular season only**; postseason
lives in a separate, non-CSV structure on their site. Unlike the other
three adapters (where postseason came free with the same endpoint),
MLB postseason would need real scraping work — deferred, see SP3_plan.md
Phase 3 notes.
"""
import csv
import io
import logging
import zipfile
from datetime import date, datetime
from typing import Optional

import httpx

from sports_passport.core.config import settings
from sports_passport.models.team import Team
from sports_passport.services.adapters.base import LeagueAdapter, ImportResult
from sports_passport.services.importer import get_league, upsert_team, upsert_venue, upsert_game

# MLB Stats API gameType -> our season_type; spring training/exhibition/all-star skipped
STATSAPI_GAME_TYPES = {"R": "regular", "F": "postseason", "D": "postseason", "L": "postseason", "W": "postseason"}

logger = logging.getLogger(__name__)

TEAMS_URL = "https://www.retrosheet.org/CurrentNames.csv"
PARKS_URL = "https://www.retrosheet.org/parkcode.txt"
GAMELOG_URL = "https://www.retrosheet.org/gamelogs/gl{season}.zip"

# Fixed field positions in a gamelog row (0-indexed); see
# https://www.retrosheet.org/gamelogs/glfields.txt
F_DATE, F_GAME_NUM, F_VIS_TEAM, F_VIS_LEAGUE = 0, 1, 3, 4
F_HOME_TEAM, F_HOME_LEAGUE, F_VIS_SCORE, F_HOME_SCORE = 6, 7, 9, 10
F_LEN_OUTS, F_DAY_NIGHT, F_PARK_ID, F_ATTENDANCE = 11, 12, 16, 17


def _franchise_id(code: str) -> int:
    """Deterministic int for a franchise code, e.g. 'ATL' -> stable id.

    Retrosheet franchise codes are 3-letter strings; encoding the ASCII
    bytes as a big-endian int gives a stable, collision-free mapping
    without a separate lookup table (max ~16.7M, fits Integer easily).
    """
    return int.from_bytes(code.encode("ascii"), "big")


def _parse_mdy(raw: str) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%m/%d/%Y").date()
    except ValueError:
        return None


def _parse_mdy_year(raw: str) -> Optional[int]:
    parsed = _parse_mdy(raw)
    return parsed.year if parsed else None


class MlbAdapter(LeagueAdapter):
    league_code = "MLB"
    source = "retrosheet"

    async def _get_text(self, url: str) -> str:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.text

    async def _get_gamelog_rows(self, season: int) -> list[list[str]]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(GAMELOG_URL.format(season=season), timeout=60.0)
            if response.status_code == 404:
                return []
            response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            name = zf.namelist()[0]
            text = zf.read(name).decode("utf-8")
        return list(csv.reader(io.StringIO(text)))

    async def import_teams(self) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)

        rows = list(csv.reader(io.StringIO(await self._get_text(TEAMS_URL))))

        by_code: dict[str, list[list[str]]] = {}
        for row in rows:
            by_code.setdefault(row[1], []).append(row)

        for code, code_rows in by_code.items():
            # Sort on parsed dates — lexicographic M/D/YYYY ordering would rank
            # "5/2/1882" after "4/19/1900" and pick a 19th-century era as latest.
            code_rows.sort(key=lambda r: _parse_mdy(r[7]) or date.min)
            latest = code_rows[-1]
            franchise, _, lg, division, city_era, nickname = latest[:6]
            start_years = [_parse_mdy_year(r[7]) for r in code_rows]
            end_years = [_parse_mdy_year(r[8]) for r in code_rows]
            still_active = any(not r[8] for r in code_rows)

            _, created = upsert_team(
                self.db,
                source=self.source,
                source_team_id=code,
                league_id=league.id,
                name=f"{city_era} {nickname}".strip(),
                nickname=nickname,
                abbreviation=code,
                city=latest[9] or None,
                state=latest[10] or None,
                conference=lg or None,
                division=division or None,
                franchise_id=_franchise_id(franchise),
                first_season=min(y for y in start_years if y is not None),
                last_season=None if still_active else max(y for y in end_years if y is not None),
            )
            if created:
                result.teams_imported += 1

        self.db.commit()
        return result

    async def _park_lookup(self) -> dict[str, dict]:
        rows = csv.DictReader(io.StringIO(await self._get_text(PARKS_URL)))
        return {row["PARKID"]: row for row in rows}

    def _team_lookup(self, league_id: int) -> dict[str, int]:
        teams = self.db.query(Team).filter(Team.league_id == league_id).all()
        return {t.source_team_id: t.id for t in teams if t.source_team_id}

    def _upsert_row(
        self, league_id: int, row: list[str], season: int,
        by_code: dict, parks: dict, venue_cache: dict, result: ImportResult,
    ) -> None:
        vis_code, home_code = row[F_VIS_TEAM], row[F_HOME_TEAM]
        away_id = by_code.get(vis_code)
        home_id = by_code.get(home_code)
        if away_id is None or home_id is None:
            result.errors.append(f"game {row[F_DATE]} {vis_code}@{home_code}: unmatched team")
            return

        try:
            start_date = datetime.strptime(row[F_DATE], "%Y%m%d")
        except ValueError:
            result.errors.append(f"game {row[F_DATE]}: bad date")
            return

        park_id = row[F_PARK_ID]
        venue_id = venue_cache.get(park_id)
        if venue_id is None and park_id:
            park = parks.get(park_id, {})
            venue, created = upsert_venue(
                self.db,
                source=self.source,
                source_venue_id=park_id,
                name=park.get("NAME") or park_id,
                city=park.get("CITY") or None,
                state=park.get("STATE") or None,
            )
            venue_id = venue.id
            venue_cache[park_id] = venue_id
            if created:
                result.venues_imported += 1

        try:
            length_outs = int(row[F_LEN_OUTS])
        except (ValueError, IndexError):
            length_outs = 54
        innings = length_outs // 6 + (1 if length_outs % 6 else 0)
        overtime_flag = str(innings) if innings > 9 else None

        attendance = None
        if row[F_ATTENDANCE].strip().isdigit():
            attendance = int(row[F_ATTENDANCE])
            if attendance <= 0:
                attendance = None

        game_number = row[F_GAME_NUM]  # "0"=single, "1"/"2"/"3"/"A"/"B"=doubleheader games
        source_game_id = f"{row[F_DATE]}_{vis_code}_{home_code}_{game_number}"

        _, created = upsert_game(
            self.db,
            source=self.source,
            source_game_id=source_game_id,
            league_id=league_id,
            home_team_id=home_id,
            away_team_id=away_id,
            home_score=int(row[F_HOME_SCORE]),
            away_score=int(row[F_VIS_SCORE]),
            start_date=start_date,
            has_time=False,
            season=season,
            season_type="regular",
            venue_id=venue_id,
            neutral_site=False,
            attendance=attendance,
            overtime_flag=overtime_flag,
        )
        if created:
            result.games_imported += 1
        else:
            result.games_updated += 1

    async def import_season(self, season: int) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)
        by_code = self._team_lookup(league.id)
        parks = await self._park_lookup()
        venue_cache: dict[str, int] = {}

        rows = await self._get_gamelog_rows(season)
        for row in rows:
            self._upsert_row(league.id, row, season, by_code, parks, venue_cache, result)

        self.db.commit()
        logger.info("MLB season %s: %s games imported, %s updated",
                    season, result.games_imported, result.games_updated)
        return result

    async def import_historical(self, start_season: int, end_season: int) -> ImportResult:
        result = ImportResult(league=self.league_code)
        result.merge(await self.import_teams())
        for season in range(start_season, end_season + 1):
            result.merge(await self.import_season(season))
        return result

    def _upsert_statsapi_game(
        self, league_id: int, game: dict, by_code: dict, venue_cache: dict, result: ImportResult,
    ) -> None:
        season_type = STATSAPI_GAME_TYPES.get(game.get("gameType"))
        if season_type is None:  # spring training / exhibition / all-star
            return

        away_team = game["teams"]["away"]["team"]
        home_team = game["teams"]["home"]["team"]
        vis_code = (away_team.get("teamCode") or "").upper()
        home_code = (home_team.get("teamCode") or "").upper()
        away_id = by_code.get(vis_code)
        home_id = by_code.get(home_code)
        if away_id is None or home_id is None:
            result.errors.append(f"game {game.get('gamePk')}: unmatched team {vis_code}@{home_code}")
            return

        official_date = (game.get("officialDate") or "").replace("-", "")
        game_number = "0" if game.get("doubleHeader") == "N" else str(game.get("gameNumber", 1))
        source_game_id = f"{official_date}_{vis_code}_{home_code}_{game_number}"

        try:
            start_date = datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00")).replace(tzinfo=None)
        except (KeyError, ValueError):
            result.errors.append(f"game {game.get('gamePk')}: bad date")
            return

        venue_name = (game.get("venue") or {}).get("name")
        venue_id = venue_cache.get(venue_name)
        if venue_id is None and venue_name:
            venue, created = upsert_venue(
                self.db, source=self.source, source_venue_id=venue_name, name=venue_name,
            )
            venue_id = venue.id
            venue_cache[venue_name] = venue_id
            if created:
                result.venues_imported += 1

        _, created = upsert_game(
            self.db,
            source=self.source,
            source_game_id=source_game_id,
            league_id=league_id,
            home_team_id=home_id,
            away_team_id=away_id,
            home_score=game["teams"]["home"].get("score"),
            away_score=game["teams"]["away"].get("score"),
            start_date=start_date,
            has_time=True,
            season=int(game["season"]),
            season_type=season_type,
            venue_id=venue_id,
            neutral_site=False,
        )
        if created:
            result.games_imported += 1
        else:
            result.games_updated += 1

    async def _fetch_schedule(self, start: date, end: date) -> dict:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(
                f"{settings.mlb_api_url}/schedule",
                params={
                    "sportId": 1,
                    "startDate": start.isoformat(),
                    "endDate": end.isoformat(),
                    "hydrate": "team,venue",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def sync_recent(self, since: date) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)
        by_code = self._team_lookup(league.id)
        venue_cache: dict[str, int] = {}

        payload = await self._fetch_schedule(since, date.today())

        for date_entry in payload.get("dates", []):
            for game in date_entry.get("games", []):
                self._upsert_statsapi_game(league.id, game, by_code, venue_cache, result)

        self.db.commit()
        return result
