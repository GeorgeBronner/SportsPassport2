"""NFL adapter — nflverse, plus a Kaggle "Spreadspoke" bulk backfill.

Two sources, split on a hard season boundary so they can never disagree about
the same game — the same shape mls.py uses:

- **1999-present — nflverse** (`github.com/nflverse/nfldata`), free, keyless,
  community-maintained, the authority for teams, games and ongoing sync.
  `games.csv` carries the full schedule including the in-progress season.

    Games:  https://github.com/nflverse/nfldata/raw/master/data/games.csv
    Teams:  https://github.com/nflverse/nfldata/raw/master/data/teams.csv
    (teams.csv is 2002-present; abbreviations are stable back to 1999.)

- **1970-1998 — Kaggle "NFL scores and betting data"** (tobycrabtree),
  `data/raw/nfl/spreadspoke_scores.csv`, a one-shot historical file nflverse
  does not cover. A 2026-07-11 decision deferred this era because the file
  had gone behind a Kaggle login; re-checked 2026-08-01 and the public
  download API serves it unauthenticated again, so the gap is now closed.
  Note that only `GET` works on that URL — a `HEAD` probe 404s.

The boundary is enforced in both directions (`FIRST_NFLVERSE_SEASON`), and on
the **season** rather than the date, so the January-1999 playoffs of the 1998
season stay on the Spreadspoke side with the rest of their season.

Validated against nflverse on the 1999-2024 overlap: 6,991 games each, with
per-season counts identical, so Spreadspoke's game set is trustworthy. Its
1970-1998 slice has no null date, score or stadium, no unparseable date and no
duplicate (date, home, away) key, and its per-season counts reproduce the 1982
and 1987 strikes, the 1978 16-game expansion and 1993's 18 weeks. Its metadata
is not uniformly so — see the caveats below.

`nfl_team_id` from teams.csv is stable across relocations (e.g. STL/LA
Rams both carry 2510) and is stored as our `franchise_id`; the abbreviation
itself is the per-era team identity (STL and LA Rams are separate team
rows), matching the CFB/NHL pattern. `gametime` in the nflverse data is US
Eastern local time for every game regardless of where it is played, so
`_parse_start` converts it to UTC — `games.start_date` is defined as UTC
(SP3_plan.md §3) and the API serializer stamps an explicit UTC offset on
it, so storing Eastern here would publish a time 4-5 hours off.

Spreadspoke caveats, all handled here:

- **It carries no kickoff time at all**, so the whole era imports date-only
  (`has_time=False`) via `local_time.date_only()` — the same treatment the MLS
  Kaggle era and the NBA's pre-1996 rows get, and the reason issue #8 exists.
- It has **no attendance and no overtime column**; both stay null for the era.
- Its `stadium` column is a *physical-building* name rather than the name the
  building carried at the time — one modern name is applied across a
  building's whole life ("Cinergy Field" for Riverfront, "Ralph Wilson
  Stadium" for Rich, "Sun Life Stadium" for Joe Robbie). That is useful,
  since it behaves like the stable venue key neither source otherwise
  publishes, but a handful of rows use the era name instead, so
  `SPREADSPOKE_VENUE_IDS` maps every spelling onto one id.
- **One real defect**: Arizona Cardinals home games from 1994-1998 are labelled
  "University of Phoenix Stadium", a building that did not open until 2006 —
  they played at Sun Devil Stadium, which the 1988-1993 "Phoenix Cardinals"
  rows name correctly. Confirmed independently on the 1999+ overlap, where 55
  rows under that name resolve to PHO99. `_spreadspoke_venue_id` overrides it.
- Team and venue names are era-specific ("Houston Oilers", "Anaheim Stadium"),
  so both go through explicit maps below rather than being matched loosely.

Both eras share `source = "nflverse"`. That is deliberate rather than
cosmetic: 31 of the 64 pre-1999 stadiums are buildings nflverse also knows,
and `upsert_venue` keys on `(source, source_venue_id)` — a separate source
string for the historical era would mint a second Three Rivers Stadium
instead of joining the row the modern era already created. Historical game
ids are prefixed `spreadspoke-` so they cannot collide with an nflverse
`game_id`, the way the MLS gap era uses `kaggle-`.

One known limitation, left as-is: a team's era is stored as a single
(`first_season`, `last_season`) span, so an identity used in two separate
stretches reads as one continuous run. Adding the historical era makes that
visible for OAK (Oakland 1970-1981 and 1995-2019, with the Los Angeles years
in between carried by its own LA-RAIDERS row) and CLE (the 1996-1998 hiatus).
Individual games are attributed correctly in every case; only the summary span
overreaches, and narrowing it would need a schema change to hold multiple
ranges per team.
"""
import csv
import io
import logging
import os
import re
from datetime import date, datetime

from sports_passport.core.config import settings
from sports_passport.models.team import Team
from sports_passport.services.adapters import local_time, venue_seed
from sports_passport.services.adapters.base import ImportResult, LeagueAdapter
from sports_passport.services.importer import get_league, upsert_game, upsert_team, upsert_venue

logger = logging.getLogger(__name__)

GAMES_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
TEAMS_URL = "https://github.com/nflverse/nfldata/raw/master/data/teams.csv"
GAME_TYPES = {
    "REG": "regular",
    "WC": "postseason",
    "DIV": "postseason",
    "CON": "postseason",
    "SB": "postseason",
}

# nflverse's first season. Spreadspoke covers everything earlier; neither
# source is consulted outside its own range, so no game can arrive from both.
FIRST_NFLVERSE_SEASON = 1999
FIRST_SPREADSPOKE_SEASON = 1970

# Spreadspoke's full team name -> the team identity that owns that era. 31 of
# the 38 names in 1970-1998 map onto an abbreviation nflverse already uses
# (WAS spans every Washington rename, OAK covers both Oakland stints, CLE the
# pre-1996 Browns); the rest are minted by HISTORICAL_TEAMS below, in each case
# because the obvious abbreviation belongs to a different modern club.
SPREADSPOKE_TEAM_ALIASES = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Colts": "BAL-COLTS",
    "Baltimore Ravens": "BAL",
    "Boston Patriots": "BOS",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Oilers": "HOU-OILERS",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    # Same city and same name as the 2016-2019 nflverse "LA" Rams, so one row —
    # consistent with OAK covering both Oakland Raiders stints.
    "Los Angeles Raiders": "LA-RAIDERS",
    "Los Angeles Rams": "LA",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Oakland Raiders": "OAK",
    "Philadelphia Eagles": "PHI",
    "Phoenix Cardinals": "PHO",
    "Pittsburgh Steelers": "PIT",
    "San Diego Chargers": "SD",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "St. Louis Cardinals": "STL-CARDS",
    "St. Louis Rams": "STL",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Oilers": "TEN-OILERS",
    "Washington Redskins": "WAS",
}

# Clubs that stopped existing under that identity before 1999, so nflverse has
# no row for them. `franchise_id` is the modern successor's `nfl_team_id`, so
# the passport still reads Oilers -> Titans as one franchise — exactly how
# nflverse itself treats the STL/LA Rams.
HISTORICAL_TEAMS = {
    "BAL-COLTS": {
        "name": "Baltimore Colts", "nickname": "Colts", "abbreviation": "BAL",
        "franchise_id": 2200, "first_season": 1953, "last_season": 1983,
    },
    "BOS": {
        "name": "Boston Patriots", "nickname": "Patriots", "abbreviation": "BOS",
        "franchise_id": 3200, "first_season": 1960, "last_season": 1970,
    },
    "HOU-OILERS": {
        "name": "Houston Oilers", "nickname": "Oilers", "abbreviation": "HOU",
        "franchise_id": 2100, "first_season": 1960, "last_season": 1996,
    },
    "LA-RAIDERS": {
        "name": "Los Angeles Raiders", "nickname": "Raiders", "abbreviation": "LA",
        "franchise_id": 2520, "first_season": 1982, "last_season": 1994,
    },
    "PHO": {
        "name": "Phoenix Cardinals", "nickname": "Cardinals", "abbreviation": "PHO",
        "franchise_id": 3800, "first_season": 1988, "last_season": 1993,
    },
    "STL-CARDS": {
        "name": "St. Louis Cardinals", "nickname": "Cardinals", "abbreviation": "STL",
        "franchise_id": 3800, "first_season": 1960, "last_season": 1987,
    },
    "TEN-OILERS": {
        "name": "Tennessee Oilers", "nickname": "Oilers", "abbreviation": "TEN",
        "franchise_id": 2100, "first_season": 1997, "last_season": 1998,
    },
}

# Spreadspoke stadium name -> the venue key both eras share. The 31 ids without
# a `hist-` prefix are nflverse `stadium_id`s, derived empirically by matching
# the 1999-2024 overlap on date + both scores + home team, so a pre-1999 game
# lands on the venue row the modern era already created rather than a duplicate
# pin on the map. The `hist-` ids are buildings nflverse never saw, and are
# prefixed so they can never collide with a real nflverse id.
SPREADSPOKE_VENUE_IDS = {
    "Anaheim Stadium": "hist-anaheim",
    "Arrowhead Stadium": "KAN00",
    "Atlanta-Fulton County Stadium": "hist-atlanta-fulton",
    "Bank of America Stadium": "CAR00",
    "Busch Memorial Stadium": "hist-busch",
    "California Memorial Stadium": "hist-cal-memorial",
    "Candlestick Park": "SFO00",
    "Cinergy Field": "CIN99",
    "Cleveland Municipal Stadium": "hist-cleveland-municipal",
    "Cotton Bowl": "hist-cotton-bowl",
    "Edward Jones Dome": "STL00",
    "EverBank Field": "JAX00",
    "FedEx Field": "WAS00",
    "Foxboro Stadium": "BOS99",
    "Georgia Dome": "ATL00",
    "Giants Stadium": "NYC00",
    "Harvard Stadium": "hist-harvard",
    "Houston Astrodome": "hist-astrodome",
    # Tampa Stadium under its 1996-98 naming-rights name; both spellings appear.
    "Houlihan's Stadium": "hist-tampa-stadium",
    "Tampa Stadium": "hist-tampa-stadium",
    "Hubert H. Humphrey Metrodome": "MIN00",
    "Husky Stadium": "SEA99",
    # Qualcomm Stadium under its pre-1997 name.
    "Jack Murphy Stadium": "SDG00",
    # Hard Rock Stadium under two of its earlier names.
    "Joe Robbie Stadium": "MIA00",
    "Pro Player Stadium": "MIA00",
    "Sun Life Stadium": "MIA00",
    "Kansas City Municipal Stadium": "hist-kc-municipal",
    "Kezar Stadium": "hist-kezar",
    "Lambeau Field": "GNB00",
    "Liberty Bowl Memorial Stadium": "hist-liberty-bowl",
    "Los Angeles Memorial Coliseum": "LAX99",
    "Louisiana Superdome": "NOR00",
    "M&T Bank Stadium": "BAL00",
    "Memorial Stadium (Baltimore)": "hist-memorial-baltimore",
    "Memorial Stadium (Clemson)": "hist-memorial-clemson",
    "Metropolitan Stadium": "hist-metropolitan",
    "Mile High Stadium": "DEN99",
    "Milwaukee County Stadium": "hist-milwaukee-county",
    "Oakland Coliseum": "OAK00",
    "Orange Bowl": "hist-orange-bowl",
    "Pontiac Silverdome": "DET99",
    "Qualcomm Stadium": "SDG00",
    "RCA Dome": "IND99",
    "RFK Memorial Stadium": "hist-rfk",
    "Ralph Wilson Stadium": "BUF00",
    "Raymond James Stadium": "TAM00",
    "Rice Stadium": "hist-rice",
    "Rose Bowl": "hist-rose-bowl",
    "Seattle Kingdome": "SEA98",
    "Shea Stadium": "hist-shea",
    "Soldier Field": "CHI98",
    "Stanford Stadium": "hist-stanford",
    "Sun Devil Stadium": "PHO99",
    "Texas Stadium": "DAL99",
    "Three Rivers Stadium": "PIT99",
    "Tiger Stadium": "hist-tiger-detroit",
    "Tulane Stadium": "hist-tulane",
    "University of Phoenix Stadium": "PHO00",
    "Vanderbilt Stadium": "hist-vanderbilt",
    "Veterans Stadium": "PHI99",
    "War Memorial Stadium": "hist-war-memorial",
    "Wrigley Field": "hist-wrigley",
    "Yale Bowl": "hist-yale-bowl",
    "Yankee Stadium": "hist-yankee",
}

# See the "one real defect" note in the module docstring: State Farm Stadium
# (PHO00, opened 2006) is stamped on Cardinals home games back to 1994. Every
# Cardinals home game before this season was played at Sun Devil Stadium.
FIRST_CARDINALS_GLENDALE_SEASON = 2006
SUN_DEVIL_STADIUM_ID = "PHO99"

SPREADSPOKE_PLAYOFF_WEEKS = {"Wildcard", "Division", "Conference", "Superbowl"}


class NflAdapter(LeagueAdapter):
    league_code = "NFL"
    source = "nflverse"

    http_client_kwargs = {"follow_redirects": True}

    async def _get_csv(self, url: str) -> list[dict]:
        response = await self.http.get(url)
        response.raise_for_status()
        return list(csv.DictReader(io.StringIO(response.text)))

    async def import_teams(
        self, historical_seasons: dict[str, list[int]] | None = None
    ) -> ImportResult:
        """Upsert every team, from nflverse and optionally the Spreadspoke era.

        `historical_seasons` maps our team key -> the pre-1999 seasons that key
        played, and is supplied by `import_historical` when the backfill is in
        range. It does two things: it mints the HISTORICAL_TEAMS rows that
        nflverse has never heard of, and it widens `first_season` on the ~31
        keys both eras share. Without it every pre-1999 club would still claim
        `first_season=1999` once its games had been imported.
        """
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

        for key, seasons in (historical_seasons or {}).items():
            seasons_by_abbrev.setdefault(key, []).extend(seasons)

        # `first_season` only ever moves earlier. Without this, importing a
        # range nflverse owns — `import_historical(2020, 2026)` from the admin
        # screen, say — would recompute every shared club's debut from nflverse
        # alone and quietly reset the 31 teams the 1970-1998 backfill had
        # widened, since upsert_team overwrites any non-None field.
        known_first = {
            t.source_team_id: t.first_season
            for t in self.db.query(Team).filter(Team.league_id == league.id).all()
            if t.first_season is not None
        }

        for key, seasons in seasons_by_abbrev.items():
            historical = HISTORICAL_TEAMS.get(key)
            if historical:
                # A defunct identity: its own metadata, and its era is a matter
                # of record rather than of which rows happen to be imported.
                fields = dict(historical)
            else:
                meta = team_meta.get(key, {})
                last_season = max(seasons)
                fields = {
                    "name": meta.get("full") or key,
                    "nickname": meta.get("nickname"),
                    "abbreviation": key,
                    "franchise_id": int(meta["nfl_team_id"]) if meta.get("nfl_team_id") else None,
                    "first_season": min(seasons + [known_first.get(key, min(seasons))]),
                    "last_season": None if last_season == current_season else last_season,
                }
            _, created = upsert_team(
                self.db,
                source=self.source,
                source_team_id=key,
                league_id=league.id,
                **fields,
            )
            if created:
                result.teams_imported += 1

        self.db.commit()
        return result

    def _team_lookup(self, league_id: int) -> dict[str, int]:
        """Our team key -> team.id.

        Keyed on `source_team_id`, not `abbreviation`: the two are identical for
        nflverse rows, but the historical era deliberately reuses abbreviations
        (the Oilers really were "HOU", the Baltimore Colts "BAL"), so keying on
        the abbreviation would let a defunct club shadow the modern one that
        inherited its code and silently misfile every Texans or Ravens game.
        """
        teams = self.db.query(Team).filter(Team.league_id == league_id).all()
        return {t.source_team_id: t.id for t in teams if t.source_team_id}

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
                # The seed wins where it knows the building, so both eras agree
                # on one label. nflverse names a stadium by its naming-rights
                # deal of the moment, so letting it write here made the map pin
                # flip (Arrowhead <-> GEHA Field, Metrodome <-> Mall of America
                # Field) depending on which import ran last. `stadium` is still
                # the fallback for a ground the seed has not caught up with.
                name=(seed["name"] if seed else row.get("stadium") or stadium_id),
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
        min_season: int | None = None, max_season: int | None = None,
        since: date | None = None,
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
        logger.info(
            "NFL import: %s games imported, %s updated",
            result.games_imported,
            result.games_updated,
        )

    # ---------------------------------------------------------- Spreadspoke

    def _read_spreadspoke_csv(self) -> list[dict]:
        path = os.path.join(settings.data_dir, "raw", "nfl", "spreadspoke_scores.csv")
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"NFL bulk file not found at {path}. Download the Kaggle "
                '"NFL scores and betting data" dataset (tobycrabtree) and extract '
                "spreadspoke_scores.csv there:\n"
                "  curl -L -o nfl.zip https://www.kaggle.com/api/v1/datasets/download/"
                "tobycrabtree/nfl-scores-and-betting-data\n"
                "(GET only — a HEAD request on that URL 404s.) Only seasons before "
                f"{FIRST_NFLVERSE_SEASON} need it; later seasons come from nflverse."
            )
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def _spreadspoke_rows(self, start_season: int, end_season: int) -> list[dict]:
        """The rows this run owns: FIRST_SPREADSPOKE_SEASON up to (not
        including) FIRST_NFLVERSE_SEASON, intersected with what was asked for.

        Both ends are clamped. The file actually starts in 1966, three seasons
        before the merger, but this project's floor is 1970 and only 1970-1998
        was validated — so `import_historical(1850, 1998)`, which `admin.py`
        happily accepts, must not quietly pull in 728 pre-merger AFL games
        whose grounds (Balboa Stadium, Fenway Park, Pitt Stadium...) are
        deliberately absent from SPREADSPOKE_VENUE_IDS.
        """
        floor = max(start_season, FIRST_SPREADSPOKE_SEASON)
        rows = []
        for row in self._read_spreadspoke_csv():
            try:
                season = int(row["schedule_season"])
            except (KeyError, TypeError, ValueError):
                continue
            if floor <= season <= end_season and season < FIRST_NFLVERSE_SEASON:
                rows.append(row)
        return rows

    def _spreadspoke_venue_id(
        self,
        row: dict,
        season: int,
        cache: dict[str, int | None],
        unmapped: set[str],
        result: ImportResult,
    ) -> int | None:
        name = (row.get("stadium") or "").strip()
        if not name:
            return None

        stadium_id = SPREADSPOKE_VENUE_IDS.get(name)
        if stadium_id is None:
            # Once per building, not once per game: an unmapped ground is one
            # fact about the map, and a season of home games would otherwise
            # bury every other error in the run.
            if name not in unmapped:
                unmapped.add(name)
                result.errors.append(f"{season}: unmapped stadium {name!r}")
            return None
        # The one systematic venue defect in this file — see the module docstring.
        if stadium_id == "PHO00" and season < FIRST_CARDINALS_GLENDALE_SEASON:
            stadium_id = SUN_DEVIL_STADIUM_ID

        if stadium_id in cache:
            return cache[stadium_id]
        seed = venue_seed.nfl_stadiums().get(stadium_id)
        if seed is None:
            result.errors.append(f"{season}: stadium {stadium_id} missing from nfl_stadiums.csv")
            cache[stadium_id] = None
            return None
        venue, created = upsert_venue(
            self.db,
            source=self.source,
            source_venue_id=stadium_id,
            name=seed["name"],
            **venue_seed.venue_fields(seed),
        )
        if created:
            result.venues_imported += 1
        cache[stadium_id] = venue.id
        return venue.id

    def _import_spreadspoke(
        self, rows: list[dict], result: ImportResult, by_key: dict[str, int]
    ) -> None:
        league = get_league(self.db, self.league_code)
        venue_cache: dict[str, int | None] = {}
        unmapped_venues: set[str] = set()

        for row in rows:
            season = int(row["schedule_season"])
            home_raw = (row.get("team_home") or "").strip()
            away_raw = (row.get("team_away") or "").strip()
            home_id = by_key.get(SPREADSPOKE_TEAM_ALIASES.get(home_raw, ""))
            away_id = by_key.get(SPREADSPOKE_TEAM_ALIASES.get(away_raw, ""))
            if home_id is None or away_id is None:
                result.errors.append(f"{season} {away_raw} @ {home_raw}: unmatched team")
                continue

            game_day = self._parse_spreadspoke_date(row.get("schedule_date"))
            if game_day is None:
                result.errors.append(
                    f"{season} {away_raw} @ {home_raw}: bad date {row.get('schedule_date')!r}"
                )
                continue

            week_raw = (row.get("schedule_week") or "").strip()
            _, created = upsert_game(
                self.db,
                source=self.source,
                # No stable id in this file, so key on the natural one. Verified
                # unique across 1970-1998.
                source_game_id=(
                    f"spreadspoke-{game_day:%Y-%m-%d}-"
                    f"{_slug(home_raw)}-{_slug(away_raw)}"
                ),
                league_id=league.id,
                home_team_id=home_id,
                away_team_id=away_id,
                home_score=_int_or_none(row.get("score_home")),
                away_score=_int_or_none(row.get("score_away")),
                # The file carries no kickoff time at all, so the whole era is
                # parked date-only at noon rather than midnight (issue #8).
                start_date=local_time.date_only(game_day),
                has_time=False,
                season=season,
                season_type=(
                    "postseason"
                    if row.get("schedule_playoff") == "TRUE"
                    or week_raw in SPREADSPOKE_PLAYOFF_WEEKS
                    else "regular"
                ),
                # Playoff rounds are named, not numbered, in this file; the
                # round is carried by season_type instead of inventing a number.
                week=int(week_raw) if week_raw.isdigit() else None,
                venue_id=self._spreadspoke_venue_id(
                    row, season, venue_cache, unmapped_venues, result
                ),
                neutral_site=row.get("stadium_neutral") == "TRUE",
            )
            if created:
                result.games_imported += 1
            else:
                result.games_updated += 1
        self.db.commit()
        logger.info(
            "NFL Spreadspoke import: %s games imported, %s updated",
            result.games_imported, result.games_updated,
        )

    # ------------------------------------------------------------- Contract

    async def import_historical(self, start_season: int, end_season: int) -> ImportResult:
        result = ImportResult(league=self.league_code)

        rows = (
            self._spreadspoke_rows(start_season, end_season)
            if start_season < FIRST_NFLVERSE_SEASON
            else []
        )
        # Teams first: both import paths resolve games against existing team
        # rows, so on a fresh database this would otherwise report success
        # having imported nothing but errors.
        historical_seasons: dict[str, list[int]] = {}
        for row in rows:
            key = SPREADSPOKE_TEAM_ALIASES.get((row.get("team_home") or "").strip())
            away = SPREADSPOKE_TEAM_ALIASES.get((row.get("team_away") or "").strip())
            for k in (key, away):
                if k:
                    historical_seasons.setdefault(k, []).append(int(row["schedule_season"]))
        result.merge(await self.import_teams(historical_seasons))

        if rows:
            league = get_league(self.db, self.league_code)
            self._import_spreadspoke(rows, result, self._team_lookup(league.id))

        if end_season >= FIRST_NFLVERSE_SEASON:
            await self._import_games(
                result,
                min_season=max(start_season, FIRST_NFLVERSE_SEASON),
                max_season=end_season,
            )
        return result

    async def sync_recent(self, since: date) -> ImportResult:
        result = ImportResult(league=self.league_code)
        await self._import_games(result, since=since)
        return result

    @staticmethod
    def _parse_spreadspoke_date(raw: str | None) -> datetime | None:
        """The local game day, written `M/D/YYYY`. No time component exists."""
        try:
            return datetime.strptime((raw or "").strip(), "%m/%d/%Y")
        except ValueError:
            return None

    @staticmethod
    def _parse_start(row: dict) -> datetime | None:
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
            # and the row goes in with has_time=False, so it is parked
            # date-only rather than being shifted into the previous day.
            return local_time.date_only(datetime.fromisoformat(gameday))
        except ValueError:
            return None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _int_or_none(value: str | None) -> int | None:
    """Parse a score, treating anything unparseable as absent.

    `int()` rather than an isdigit() guard: "--5" passes `lstrip("-").isdigit()`
    and then raises, which would abort a whole import part-way through for one
    malformed cell.
    """
    try:
        return int((value or "").strip())
    except ValueError:
        return None
