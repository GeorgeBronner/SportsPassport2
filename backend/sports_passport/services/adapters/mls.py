"""MLS adapter — American Soccer Analysis API, plus a Kaggle bulk backfill.

Two sources, split on a hard season boundary so they can never disagree about
the same game:

- **2013-present — American Soccer Analysis** (`app.americansocceranalysis.com`,
  free, keyless), the authority for teams, venues, games and ongoing sync.
  Verified live: exactly one request per season returns the complete slate
  (5,732 games 2013-2026, zero unresolved team ids, zero null scores or dates),
  `date_time_utc` is genuinely UTC (cross-checked against ESPN), and the
  `stadia` endpoint carries latitude/longitude, city and capacity directly —
  the only source in this project that hands us venue coordinates, so MLS needs
  no hand-built seed for the modern era.

- **1996-2012 — Kaggle "Major League Soccer Dataset"** (josephvm),
  `data/raw/mls/matches.csv`, a one-shot historical file ASA does not cover.
  Validated against ASA on the 2013-2022 overlap: per-season game counts match
  exactly and all 3,687 rows find an ASA twin, so its game set and scores are
  trustworthy. Its metadata is not uniformly so — see the caveats below.

The boundary is enforced in both directions (`FIRST_ASA_SEASON`): ASA is never
asked for a season before 2013, and Kaggle rows at or after it are skipped.

Kaggle caveats, all handled here:

- `time (utc)` is present on only 73% of gap-era rows and, where present,
  agrees with ASA exactly 80.6% of the time — the rest scatters +/-30 to 210
  minutes, which is noise rather than a timezone offset. The whole era is
  therefore imported date-only (`has_time=False`), which is also what issue #7
  did with the NBA's pre-1996 placeholder times.
- The `date` column is the **local** game day, not the UTC one — confirmed
  because 93.5% of games kicking off 00:00-05:59 UTC carry a Kaggle date one
  day earlier. Reading it as UTC would shift every late kickoff a day forward,
  which is exactly the bug class of issues #5 and #7.
- Team and venue names drift across eras ("KC Wiz" -> "Sporting Kansas City",
  five spellings of RFK Stadium), so both go through explicit canonical maps
  below rather than being matched loosely.
- 2001-2003 carries almost no venue at all (2002 has none) — a hole ESPN shares,
  suggesting a common origin. Those games import with a null venue.

Compliance: ASA publishes no formal terms, but maintains the MIT-licensed
`itscalledsoccer` Python and R clients against this same API, so programmatic
use is plainly intended. Treated like ESPN elsewhere in this project —
descriptive User-Agent, and a backfill that is 14 requests rather than a crawl.
"""
import csv
import logging
import os
import re
from datetime import date, datetime
from typing import Any, Optional

from sports_passport.core.config import settings
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue
from sports_passport.services.adapters import local_time, venue_seed
from sports_passport.services.adapters.base import LeagueAdapter, ImportResult
from sports_passport.services.importer import get_league, upsert_team, upsert_venue, upsert_game

logger = logging.getLogger(__name__)

ASA_BASE = "https://app.americansocceranalysis.com/api/v1/mls"

# ASA's first season. Kaggle covers everything earlier; neither source is
# consulted outside its own range, so no game can arrive from both.
FIRST_ASA_SEASON = 2013
FIRST_MLS_SEASON = 1996

# Kaggle team-name variants -> the ASA team name that owns the franchise's
# history. MLS itself treats the current San Jose Earthquakes as continuous
# with the 1996-2005 club (Houston is a separate expansion side that inherited
# the roster), which is why both San Jose spellings fold together here.
KAGGLE_TEAM_ALIASES = {
    "Chicago": "Chicago Fire FC",
    "Chicago Fire FC": "Chicago Fire FC",
    "Chivas USA": "Chivas USA",
    "Colorado": "Colorado Rapids",
    "Colorado Rapids": "Colorado Rapids",
    "Columbus": "Columbus Crew",
    "Columbus Crew SC": "Columbus Crew",
    "D.C. United": "D.C. United",
    "DC United": "D.C. United",
    "Dallas": "FC Dallas",
    "FC Dallas": "FC Dallas",
    "Houston Dynamo": "Houston Dynamo FC",
    "KC Wiz": "Sporting Kansas City",
    "KC Wizards": "Sporting Kansas City",
    "LA Galaxy": "LA Galaxy",
    "MetroStars": "New York Red Bulls",
    "Montreal Impact": "CF Montréal",
    "New England": "New England Revolution",
    "New England Revolution": "New England Revolution",
    "New York Red Bulls": "New York Red Bulls",
    "Philadelphia Union": "Philadelphia Union",
    "Portland Timbers": "Portland Timbers FC",
    "Real Salt Lake": "Real Salt Lake",
    "San Jose": "San Jose Earthquakes",
    "San Jose Earthquakes": "San Jose Earthquakes",
    "Seattle Sounders FC": "Seattle Sounders FC",
    "Sporting Kansas City": "Sporting Kansas City",
    "Toronto FC": "Toronto FC",
    "Vancouver Whitecaps": "Vancouver Whitecaps FC",
}

# Folded after the 2001 season, so ASA — which starts in 2013 — has no row for
# either. They get their own team rows rather than being dropped, because games
# at Houlihan's Stadium and Lockhart Stadium are still games someone attended.
DEFUNCT_TEAMS = {
    "Tampa Bay": {
        "name": "Tampa Bay Mutiny",
        "abbreviation": "TBM",
        "city": "Tampa",
        "state": "FL",
        "first_season": 1996,
        "last_season": 2001,
    },
    "Miami": {
        "name": "Miami Fusion",
        "abbreviation": "MIA",
        "city": "Fort Lauderdale",
        "state": "FL",
        "first_season": 1998,
        "last_season": 2001,
    },
}

# Exhibition sides that appear as if they were clubs; the 2004 All-Star game is
# the only row involved.
NON_CLUB_TEAMS = {"East All-Stars", "West All-Stars"}

# Kaggle venue string -> canonical building. Collapses naming-rights eras and
# spelling drift so one ground is one venue row. Names on the right match ASA's
# `stadia` spelling wherever ASA knows the building, so the two eras land on the
# same row; the rest are resolved through data/seed/mls_stadiums.csv.
#
# Deliberately *not* collapsed: Mile High Stadium vs Empower Field, Foxboro
# Stadium vs Gillette, Houlihan's Stadium vs Raymond James, Empire Field vs BC
# Place. Each pair is two different buildings that happen to be neighbours.
KAGGLE_VENUE_ALIASES = {
    "Robert F. Kennedy Memorial Stadium": "RFK Stadium",
    "RFK Memorial Stadium": "RFK Stadium",
    "RFK Memorial": "RFK Stadium",
    "R.F.K. Stadium": "RFK Stadium",
    "MAPFRE Stadium": "Historic Crew Stadium",
    "StubHub Center": "Dignity Health Sports Park",
    "Pizza Hut Park": "Toyota Stadium",
    "Frisco Sports & Entertainment Center": "Toyota Stadium",
    "Bridgeview Stadium": "SeatGeek Stadium",
    "CEFCU Stadium": "Spartan Stadium",
    "Qwest Field": "Lumen Field",
    "CenturyLink Field": "Lumen Field",
    "BBVA Stadium": "Shell Energy Stadium",
    "Rio Tinto Stadium": "America First Field",
    "Sports Authority Field at Mile High": "Empower Field at Mile High",
    "Stanford": "Stanford Stadium",
    "AT THE ORANGE BOWL": "Miami Orange Bowl",
    "Dallas Cowboys New Stadium": "AT&T Stadium",
    "Reliant Stadium": "NRG Stadium",
    "McAfee Coliseum": "Oakland Coliseum",
}

# Spanish for "unconfirmed" — a placeholder, not a ground.
UNKNOWN_VENUES = {"Sin confirmar"}

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
    )
}


def _canonical_venue(raw: str) -> Optional[str]:
    """Kaggle's venue string -> canonical building name, or None if unusable.

    The raw column mixes in a city suffix ("BMO Field, Toronto") and a
    neutral-site marker, either of which would otherwise split one ground
    across several venue rows.
    """
    name = re.sub(r"\s*\(Neutral Site\)\s*", "", (raw or "").strip())
    name = name.split(",")[0].strip()
    if not name or name in UNKNOWN_VENUES:
        return None
    return KAGGLE_VENUE_ALIASES.get(name, name)


def _season_type(part_of_competition: str) -> str:
    """Kaggle's free-text round label -> 'regular' | 'postseason' | 'preseason'.

    27 variants appear, differing by leading whitespace, hyphenation and an
    embedded year ("Regular Season 2015", " Conference Semi-finals",
    "MLS Cup '96"), so this matches on content rather than enumerating them.
    """
    label = (part_of_competition or "").strip().lower()
    if not label:
        return "regular"
    if "preseason" in label:
        return "preseason"
    if "regular season" in label:
        return "regular"
    return "postseason"


def _parse_kaggle_date(raw_date: str, year: int) -> Optional[datetime]:
    """The local game day. Two formats appear: '7/31/1996' and 'Friday, March 6'.

    The second carries no year, which is why `year` is passed alongside it.
    """
    value = (raw_date or "").strip()
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", value)
    if match:
        month, day, yr = int(match.group(1)), int(match.group(2)), int(match.group(3))
    else:
        match = re.match(r"^\w+day,\s*(\w+)\s+(\d{1,2})$", value)
        if not match or match.group(1) not in MONTHS:
            return None
        month, day, yr = MONTHS[match.group(1)], int(match.group(2)), year
    try:
        return datetime(yr, month, day)
    except ValueError:
        return None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class MlsAdapter(LeagueAdapter):
    league_code = "MLS"
    source = "mls"

    http_client_kwargs = {
        "headers": {"User-Agent": "SportsPassport/0.2 (personal game-attendance tracker)"}
    }

    # ------------------------------------------------------------------ ASA

    async def _get(self, path: str) -> Any:
        response = await self.http.get(f"{ASA_BASE}{path}")
        response.raise_for_status()
        return response.json()

    async def import_teams(self) -> ImportResult:
        """ASA's club list, plus the two franchises that folded before 2013."""
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)

        for row in await self._get("/teams"):
            _, created = upsert_team(
                self.db,
                source=self.source,
                source_team_id=row["team_id"],
                league_id=league.id,
                name=row.get("team_name"),
                abbreviation=row.get("team_abbreviation"),
            )
            if created:
                result.teams_imported += 1

        for key, fields in DEFUNCT_TEAMS.items():
            _, created = upsert_team(
                self.db,
                source=self.source,
                source_team_id=f"defunct-{_slug(key)}",
                league_id=league.id,
                **fields,
            )
            if created:
                result.teams_imported += 1

        self.db.commit()
        return result

    def _teams_by_name(self, league_id: int) -> dict[str, int]:
        teams = self.db.query(Team).filter(Team.league_id == league_id).all()
        return {t.name: t.id for t in teams if t.name}

    def _teams_by_source_id(self, league_id: int) -> dict[str, int]:
        teams = self.db.query(Team).filter(Team.league_id == league_id).all()
        return {t.source_team_id: t.id for t in teams}

    async def _asa_venues(self, result: ImportResult) -> tuple[dict[str, int], dict[str, str]]:
        """Upsert ASA's stadia. Returns (stadium_id -> venue.id, name -> stadium_id).

        The second mapping lets the Kaggle era reuse a venue row ASA already
        owns when both refer to the same building.
        """
        by_stadium_id: dict[str, int] = {}
        stadium_id_by_name: dict[str, str] = {}
        for row in await self._get("/stadia"):
            name = row.get("stadium_name")
            if not name:
                continue
            latitude, longitude = row.get("latitude"), row.get("longitude")
            if latitude is None or longitude is None:
                # 8 of ASA's 56 stadia carry no coordinates; the seed covers them.
                seed = venue_seed.lookup_mls_stadium(name)
                if seed:
                    latitude = float(seed["latitude"])
                    longitude = float(seed["longitude"])
            venue, created = upsert_venue(
                self.db,
                source=self.source,
                source_venue_id=row["stadium_id"],
                name=name,
                city=row.get("city"),
                state=row.get("province"),
                country=row.get("country"),
                capacity=row.get("capacity"),
                latitude=latitude,
                longitude=longitude,
            )
            by_stadium_id[row["stadium_id"]] = venue.id
            stadium_id_by_name.setdefault(name, row["stadium_id"])
            if created:
                result.venues_imported += 1
        return by_stadium_id, stadium_id_by_name

    async def _import_asa_season(self, season: int, result: ImportResult) -> None:
        league = get_league(self.db, self.league_code)
        teams = self._teams_by_source_id(league.id)
        venues, _ = await self._asa_venues(result)

        for row in await self._get(f"/games?season_name={season}"):
            home_id = teams.get(row.get("home_team_id"))
            away_id = teams.get(row.get("away_team_id"))
            if home_id is None or away_id is None:
                result.errors.append(f"game {row.get('game_id')}: unmatched team")
                continue
            try:
                start_date = datetime.strptime(row["date_time_utc"][:19], "%Y-%m-%d %H:%M:%S")
            except (KeyError, TypeError, ValueError):
                result.errors.append(f"game {row.get('game_id')}: bad date")
                continue

            _, created = upsert_game(
                self.db,
                source=self.source,
                source_game_id=row["game_id"],
                league_id=league.id,
                home_team_id=home_id,
                away_team_id=away_id,
                home_score=row.get("home_score"),
                away_score=row.get("away_score"),
                start_date=start_date,
                has_time=True,
                season=season,
                season_type="postseason" if row.get("knockout_game") else "regular",
                venue_id=venues.get(row.get("stadium_id")),
                neutral_site=False,
                attendance=row.get("attendance"),
            )
            if created:
                result.games_imported += 1
            else:
                result.games_updated += 1
        self.db.commit()

    # --------------------------------------------------------------- Kaggle

    def _read_matches_csv(self) -> list[dict]:
        path = os.path.join(settings.data_dir, "raw", "mls", "matches.csv")
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def _kaggle_venue_id(
        self,
        canonical: str,
        cache: dict[str, Optional[int]],
        stadium_id_by_name: dict[str, str],
        asa_venues: dict[str, int],
        result: ImportResult,
    ) -> Optional[int]:
        if canonical in cache:
            return cache[canonical]

        # Same building ASA already knows: reuse its row rather than minting a
        # second one under a different key.
        stadium_id = stadium_id_by_name.get(canonical)
        if stadium_id and stadium_id in asa_venues:
            cache[canonical] = asa_venues[stadium_id]
            return cache[canonical]

        seed = venue_seed.lookup_mls_stadium(canonical)
        fields = venue_seed.venue_fields(seed) if seed else {}
        venue, created = upsert_venue(
            self.db,
            source=self.source,
            source_venue_id=f"kaggle-{_slug(canonical)}",
            name=canonical,
            **fields,
        )
        if created:
            result.venues_imported += 1
            if not seed:
                result.errors.append(f"venue {canonical!r}: no coordinates in seed")
        cache[canonical] = venue.id
        return venue.id

    async def _import_kaggle(self, start_season: int, end_season: int, result: ImportResult) -> None:
        league = get_league(self.db, self.league_code)
        by_name = self._teams_by_name(league.id)
        by_source_id = self._teams_by_source_id(league.id)
        asa_venues, stadium_id_by_name = await self._asa_venues(result)
        venue_cache: dict[str, Optional[int]] = {}

        def resolve_team(raw: str) -> Optional[int]:
            raw = (raw or "").strip()
            if raw in DEFUNCT_TEAMS:
                return by_source_id.get(f"defunct-{_slug(raw)}")
            canonical = KAGGLE_TEAM_ALIASES.get(raw)
            return by_name.get(canonical) if canonical else None

        for row in self._read_matches_csv():
            try:
                season = int(row["year"])
            except (KeyError, TypeError, ValueError):
                continue
            # ASA owns everything from FIRST_ASA_SEASON on, whatever was asked for.
            if not (start_season <= season <= end_season) or season >= FIRST_ASA_SEASON:
                continue

            home_raw, away_raw = (row.get("home") or "").strip(), (row.get("away") or "").strip()
            if home_raw in NON_CLUB_TEAMS or away_raw in NON_CLUB_TEAMS:
                continue

            home_id, away_id = resolve_team(home_raw), resolve_team(away_raw)
            if home_id is None or away_id is None:
                result.errors.append(f"{season} {away_raw} @ {home_raw}: unmatched team")
                continue

            game_day = _parse_kaggle_date(row.get("date"), season)
            if game_day is None:
                result.errors.append(f"{season} {away_raw} @ {home_raw}: bad date {row.get('date')!r}")
                continue

            canonical = _canonical_venue(row.get("venue"))
            venue_id = (
                self._kaggle_venue_id(canonical, venue_cache, stadium_id_by_name, asa_venues, result)
                if canonical
                else None
            )

            # No stable id on ~27% of rows, so key on the natural one. Verified
            # unique across the era.
            source_game_id = f"kaggle-{game_day:%Y-%m-%d}-{_slug(home_raw)}-{_slug(away_raw)}"

            _, created = upsert_game(
                self.db,
                source=self.source,
                source_game_id=source_game_id,
                league_id=league.id,
                home_team_id=home_id,
                away_team_id=away_id,
                home_score=_int_or_none(row.get("home_score")),
                away_score=_int_or_none(row.get("away_score")),
                # The column is the local game day and the era's clock times are
                # unreliable, so this goes in date-only.
                start_date=local_time.date_only(game_day),
                has_time=False,
                season=season,
                season_type=_season_type(row.get("part_of_competition")),
                venue_id=venue_id,
                neutral_site="(Neutral Site)" in (row.get("venue") or ""),
                attendance=_int_or_none(row.get("attendance")),
                overtime_flag="SO" if (row.get("shootout") or "").strip() else None,
            )
            if created:
                result.games_imported += 1
            else:
                result.games_updated += 1
        self.db.commit()

    # ------------------------------------------------------------- Contract

    async def import_historical(self, start_season: int, end_season: int) -> ImportResult:
        result = ImportResult(league=self.league_code)

        if start_season < FIRST_ASA_SEASON:
            await self._import_kaggle(start_season, end_season, result)

        for season in range(max(start_season, FIRST_ASA_SEASON), end_season + 1):
            await self._import_asa_season(season, result)

        return result

    async def sync_recent(self, since: date) -> ImportResult:
        """Re-pull the seasons `since` touches. ASA publishes completed games
        only, so this fills in results rather than announcing fixtures."""
        result = ImportResult(league=self.league_code)
        for season in range(max(since.year, FIRST_ASA_SEASON), date.today().year + 1):
            await self._import_asa_season(season, result)
        return result


def _int_or_none(value: Any) -> Optional[int]:
    """Kaggle writes attendance with thousands separators and blanks for null."""
    text = str(value or "").strip().replace(",", "")
    return int(text) if text.isdigit() else None
