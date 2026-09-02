"""MLB adapter — Retrosheet (retrosheet.org) game logs + park codes.

Free, keyless, official historical record; permissive license ("recipients
are free to make any use of the data, including commercial"). Like the
CFB/NHL/NFL adapters, games are fetched live from Retrosheet's static file
server rather than downloaded once into `data/raw/` — it's a plain static
host with no rate limit or ToS concern (see docs/SP3_data_sources.md), so a
local copy buys nothing over re-fetching per import.

- Franchise/team directory (one row per team-identity era, franchise-linked
  via column 1, e.g. Montreal Expos + Washington Nationals both "WAS"):
    https://www.retrosheet.org/CurrentNames.csv
- Ballpark directory (park id -> name/city/state):
    https://www.retrosheet.org/parkcode.txt
- Season game logs (fixed-field CSV, no header, one row per game):
    https://www.retrosheet.org/gamelogs/gl{season}.zip
- Postseason game logs (same fixed-field format; each file spans ALL years
  of its series type — ws=World Series 1903-, lc=LCS 1969-, dv=Division
  Series 1981/1995-, wc=Wild Card 2012-):
    https://www.retrosheet.org/gamelogs/gl{ws,lc,dv,wc}.zip

Compliance guardrail: Retrosheet is the bulk-backfill source. The MLB
Stats API (`sync_recent`) must never be used for bulk backfill per its
terms (docs/SP3_data_sources.md) — only for small "since date" queries.

Scope note: the per-season gamelogs cover regular season only; postseason
comes from the four companion files above via `import_postseason` (all-time
files filtered to the requested season range). Spring training exists in
neither source and is skipped by `sync_recent` (see docs/open_issues.md).
"""
import asyncio
import csv
import io
import logging
import re
import zipfile
from datetime import date, datetime

import httpx

from sports_passport.core.config import settings
from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue
from sports_passport.services.adapters import local_time
from sports_passport.services.adapters.base import ImportResult, LeagueAdapter
from sports_passport.services.importer import get_league, upsert_game, upsert_team, upsert_venue

# MLB Stats API gameType -> our season_type; spring training/exhibition/all-star skipped
STATSAPI_GAME_TYPES = {
    "R": "regular",
    "F": "postseason",
    "D": "postseason",
    "L": "postseason",
    "W": "postseason",
}

logger = logging.getLogger(__name__)

TEAMS_URL = "https://www.retrosheet.org/CurrentNames.csv"
PARKS_URL = "https://www.retrosheet.org/parkcode.txt"
GAMELOG_URL = "https://www.retrosheet.org/gamelogs/gl{season}.zip"
POSTSEASON_GAMELOG_URL = "https://www.retrosheet.org/gamelogs/gl{code}.zip"
POSTSEASON_FILE_CODES = ("ws", "lc", "dv", "wc")

# MLB Stats API venue id -> Retrosheet park id, for the sync venue bridge.
#
# Sync only ever learns a venue from the Stats API, which reports the park's
# *current* name; the historical backfill keys venues on Retrosheet park ids.
# Matching the two on name breaks the moment a naming-rights deal changes the
# sign faster than Retrosheet updates parkcode.txt — which in practice is most
# of the league (Retrosheet still calls Truist Park "Suntrust Park", T-Mobile
# Park "Safeco Field", Oracle Park "AT&T Park", ...). The Stats API venue id
# survives every rename, so it is the key that keeps a synced game on the same
# row the backfill already gave a city, state and coordinates. Name matching
# remains the fallback for a venue not listed here.
#
# Every entry is a park the backfill has actually seen (or that parkcode.txt
# lists), so mapping to it never invents a venue row. Verified against
# `statsapi.mlb.com/api/v1/teams?sportId=1&hydrate=venue` on 2026-09-02.
STATSAPI_VENUE_PARK_IDS: dict[int, str] = {
    1: "ANA01",     # Angel Stadium
    2: "BAL12",     # Oriole Park at Camden Yards
    3: "BOS07",     # Fenway Park
    4: "CHI12",     # Rate Field
    5: "CLE08",     # Progressive Field
    7: "KAN06",     # Kauffman Stadium
    12: "STP01",    # Tropicana Field
    14: "TOR02",    # Rogers Centre
    15: "PHO01",    # Chase Field
    17: "CHI11",    # Wrigley Field
    19: "DEN02",    # Coors Field
    22: "LOS03",    # Dodger Stadium
    31: "PIT08",    # PNC Park
    32: "MIL06",    # American Family Field
    680: "SEA03",   # T-Mobile Park
    2392: "HOU03",  # Daikin Park
    2394: "DET05",  # Comerica Park
    2395: "SFO03",  # Oracle Park
    2529: "SAC01",  # Sutter Health Park (Athletics, 2025-)
    2602: "CIN09",  # Great American Ball Park
    2680: "SAN02",  # Petco Park
    2681: "PHI13",  # Citizens Bank Park
    2889: "STL10",  # Busch Stadium
    3289: "NYC20",  # Citi Field
    3309: "WAS11",  # Nationals Park
    3312: "MIN04",  # Target Field
    3313: "NYC21",  # Yankee Stadium
    4169: "MIA02",  # loanDepot park
    4705: "ATL03",  # Truist Park
    5325: "ARL03",  # Globe Life Field
    # Temporary homes and neutral-site parks
    2523: "TAM02",  # George M. Steinbrenner Field (Rays, 2025)
    2735: "WIL02",  # Journey Bank Ballpark, Williamsport (Little League Classic)
    2756: "BUF05",  # Sahlen Field, Buffalo (Blue Jays, 2020-21)
    3949: "BIR01",  # Rickwood Field, Birmingham (2024)
    5010: "FTB01",  # Fort Bragg Field (2016)
    5150: "SEO01",  # Gocheok Sky Dome, Seoul (2024)
    5340: "MEX02",  # Estadio Alfredo Harp Helu, Mexico City
    5381: "LON01",  # London Stadium
    5445: "DYE01",  # Field of Dreams, Dyersville
    6130: "BST01",  # Bristol Motor Speedway (2025)
}

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


def _parse_mdy(raw: str) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%m/%d/%Y").date()
    except ValueError:
        return None


def _parse_mdy_year(raw: str) -> int | None:
    parsed = _parse_mdy(raw)
    return parsed.year if parsed else None


class MlbAdapter(LeagueAdapter):
    league_code = "MLB"
    source = "retrosheet"

    http_client_kwargs = {"follow_redirects": True}

    async def _get_text(self, url: str) -> str:
        response = await self.http.get(url)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _parse_zipped_rows(content: bytes) -> list[list[str]]:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            name = zf.namelist()[0]
            text = zf.read(name).decode("utf-8")
        return list(csv.reader(io.StringIO(text)))

    async def _get_zipped_rows(self, url: str) -> list[list[str]]:
        # Retrosheet season zips are large; they get longer than the default.
        response = await self.http.get(url, timeout=60.0)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return await asyncio.to_thread(self._parse_zipped_rows, response.content)

    async def _get_gamelog_rows(self, season: int) -> list[list[str]]:
        return await self._get_zipped_rows(GAMELOG_URL.format(season=season))

    async def _get_postseason_rows(self, code: str) -> list[list[str]]:
        return await self._get_zipped_rows(POSTSEASON_GAMELOG_URL.format(code=code))

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

    @staticmethod
    def _normalize_park_name(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    @classmethod
    def _active_park_ids_by_name(cls, parks: dict[str, dict]) -> dict[str, str]:
        """Retrosheet park id keyed by normalized NAME/AKA, parks still in use only.

        Bridges the Stats API sync path (which only ever reports a venue by
        its current name) onto the same park id the Retrosheet backfill
        already keys venues on, so the two paths converge on one venue row
        instead of the sync path minting a second row under the raw name.
        A blank ``END`` in parkcode.txt means the park is still active; a
        retired park is never a candidate since sync only ever sees current
        games.
        """
        by_name: dict[str, str] = {}
        for park_id, row in parks.items():
            if row.get("END"):
                continue
            for name in (row.get("NAME"), row.get("AKA")):
                if not name:
                    continue
                key = cls._normalize_park_name(name)
                existing = by_name.get(key)
                if existing is not None and existing != park_id:
                    logger.warning(
                        "MLB: active parks %r and %r both normalize to %r; "
                        "keeping %r for the sync venue bridge",
                        existing, park_id, key, existing,
                    )
                    continue
                by_name[key] = park_id
        return by_name

    @classmethod
    def _bridge_park_id(
        cls, statsapi_venue_id: int | None, venue_name: str, park_ids_by_name: dict[str, str],
    ) -> str | None:
        """Retrosheet park id for a Stats API venue, or None if unknown.

        The venue id map wins: it is immune to the sponsor renames that make
        the name match go stale (see STATSAPI_VENUE_PARK_IDS). The name match
        is the fallback for a venue the map doesn't list yet.
        """
        park_id = STATSAPI_VENUE_PARK_IDS.get(statsapi_venue_id) if statsapi_venue_id else None
        if park_id is None:
            park_id = park_ids_by_name.get(cls._normalize_park_name(venue_name))
        return park_id

    def _team_lookup(self, league_id: int) -> dict[str, int]:
        teams = self.db.query(Team).filter(Team.league_id == league_id).all()
        return {t.source_team_id: t.id for t in teams if t.source_team_id}

    def _upsert_row(
        self, league_id: int, row: list[str], season: int,
        by_code: dict, parks: dict, venue_cache: dict, result: ImportResult,
        season_type: str = "regular",
    ) -> None:
        vis_code, home_code = row[F_VIS_TEAM], row[F_HOME_TEAM]
        away_id = by_code.get(vis_code)
        home_id = by_code.get(home_code)
        if away_id is None or home_id is None:
            result.errors.append(f"game {row[F_DATE]} {vis_code}@{home_code}: unmatched team")
            return

        try:
            # Gamelogs carry the local game day and no usable start time, so
            # the row goes in date-only (has_time=False below).
            start_date = local_time.date_only(datetime.strptime(row[F_DATE], "%Y%m%d"))
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
            season_type=season_type,
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

    async def import_postseason(self, start_season: int, end_season: int) -> ImportResult:
        """Import postseason games for a season range.

        The four postseason gamelog files each span every year of their
        series type, so this fetches four files total regardless of range
        size and filters rows by year. A game's season is the calendar year
        of its date — the MLB postseason never crosses New Year.
        """
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)
        by_code = self._team_lookup(league.id)
        parks = await self._park_lookup()
        venue_cache: dict[str, int] = {}

        for code in POSTSEASON_FILE_CODES:
            for row in await self._get_postseason_rows(code):
                if not row or not row[F_DATE][:4].isdigit():
                    continue
                season = int(row[F_DATE][:4])
                if not start_season <= season <= end_season:
                    continue
                self._upsert_row(league.id, row, season, by_code, parks, venue_cache,
                                 result, season_type="postseason")

        self.db.commit()
        logger.info("MLB postseason %s-%s: %s games imported, %s updated",
                    start_season, end_season, result.games_imported, result.games_updated)
        return result

    async def import_historical(self, start_season: int, end_season: int) -> ImportResult:
        result = ImportResult(league=self.league_code)
        result.merge(await self.import_teams())
        for season in range(start_season, end_season + 1):
            result.merge(await self.import_season(season))
        result.merge(await self.import_postseason(start_season, end_season))
        return result

    def _reconcile_legacy_venue(self, legacy_name: str, canonical_id: str) -> None:
        """Merge a venue row a pre-bridge sync already created under the raw
        API name onto the canonical Retrosheet-park-id row.

        Before the park-name bridge existed, `_upsert_statsapi_game` keyed
        every synced venue on the raw API name, so a database that's been
        syncing this park for a while may already have a
        `(source, venue_name)` row with games attached to it. Once the bridge
        takes over, upserting under `(source, canonical_id)` would otherwise
        silently orphan those games onto an abandoned row instead of
        converging them onto the historical backfill's row as intended.
        `games.venue_id` is the only FK onto `venues.id` (attendance only
        references `game_id`), so reassigning it is sufficient to merge.
        """
        legacy = (
            self.db.query(Venue)
            .filter(Venue.source == self.source, Venue.source_venue_id == legacy_name)
            .first()
        )
        if legacy is None:
            return
        canonical, _ = upsert_venue(
            self.db, source=self.source, source_venue_id=canonical_id, name=legacy.name
        )
        if canonical.id == legacy.id:
            return
        self.db.query(Game).filter(Game.venue_id == legacy.id).update({"venue_id": canonical.id})
        self.db.delete(legacy)
        self.db.flush()

    def _upsert_statsapi_game(
        self, league_id: int, game: dict, by_code: dict, venue_cache: dict,
        park_ids_by_name: dict[str, str], result: ImportResult,
    ) -> None:
        season_type = STATSAPI_GAME_TYPES.get(game.get("gameType") or "")
        if season_type is None:  # spring training / exhibition / all-star
            return

        away_team = game["teams"]["away"]["team"]
        home_team = game["teams"]["home"]["team"]
        vis_code = (away_team.get("teamCode") or "").upper()
        home_code = (home_team.get("teamCode") or "").upper()
        away_id = by_code.get(vis_code)
        home_id = by_code.get(home_code)
        if away_id is None or home_id is None:
            result.errors.append(
                f"game {game.get('gamePk')}: unmatched team {vis_code}@{home_code}"
            )
            return

        official_date = (game.get("officialDate") or "").replace("-", "")
        game_number = "0" if game.get("doubleHeader") == "N" else str(game.get("gameNumber", 1))
        source_game_id = f"{official_date}_{vis_code}_{home_code}_{game_number}"

        try:
            start_date = datetime.fromisoformat(
                game["gameDate"].replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except (KeyError, ValueError):
            result.errors.append(f"game {game.get('gamePk')}: bad date")
            return

        venue = game.get("venue") or {}
        venue_name = venue.get("name")
        venue_id = venue_cache.get(venue_name)
        if venue_id is None and venue_name:
            # Bridge to the Retrosheet park id the historical backfill already
            # keys this venue on, so the two paths converge on one row instead
            # of sync minting a second under the raw API name. A miss (a park
            # neither the id map nor parkcode.txt knows) falls back to the
            # old behavior rather than failing the sync.
            source_venue_id = self._bridge_park_id(venue.get("id"), venue_name, park_ids_by_name)
            if source_venue_id is None:
                source_venue_id = venue_name
                logger.warning(
                    "MLB sync: venue %r (Stats API id %r) matches neither "
                    "STATSAPI_VENUE_PARK_IDS nor an active Retrosheet park; "
                    "won't bridge to the historical backfill's venue row",
                    venue_name, venue.get("id"),
                )
            else:
                self._reconcile_legacy_venue(venue_name, source_venue_id)
            venue, created = upsert_venue(
                self.db, source=self.source, source_venue_id=source_venue_id, name=venue_name,
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
        response = await self.http.get(
            f"{settings.mlb_api_url}/schedule",
            params={
                "sportId": 1,
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "hydrate": "team,venue",
            },
        )
        response.raise_for_status()
        return response.json()

    async def sync_recent(self, since: date) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)
        by_code = self._team_lookup(league.id)
        venue_cache: dict[str, int] = {}
        try:
            park_ids_by_name = self._active_park_ids_by_name(await self._park_lookup())
        except httpx.HTTPError as exc:
            # The venue bridge is an enhancement over the sync path's old
            # behavior (source_venue_id=raw name), not a prerequisite for it —
            # a Retrosheet hiccup shouldn't fail the whole game/team sync.
            result.errors.append(
                f"Retrosheet parkcode.txt unavailable ({exc}); venues synced this run "
                "won't bridge to the historical backfill's rows"
            )
            logger.warning("MLB sync: parkcode.txt fetch failed, continuing without it: %s", exc)
            park_ids_by_name = {}

        payload = await self._fetch_schedule(since, date.today())

        for date_entry in payload.get("dates", []):
            for game in date_entry.get("games", []):
                self._upsert_statsapi_game(
                    league.id, game, by_code, venue_cache, park_ids_by_name, result
                )

        self.db.commit()
        return result
