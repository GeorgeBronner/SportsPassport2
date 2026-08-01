"""NBA adapter — Kaggle bulk CSV (historical) + ESPN scoreboard (sync).

The Kaggle bulk CSV needs a Kaggle login, same as the NFL Spreadspoke
dataset. The user grabbed it manually (free account, no payment) — see
backend/data/raw/nba/Games.csv (eoinamoore's "NBA Dataset: Box Scores and
Stats" on Kaggle). Unlike the other four adapters, `import_historical`
therefore parses a local file rather than fetching live; there's no other
free live bulk source to fall back to.

`sync_recent` originally targeted stats.nba.com's `scoreboardv2`. That was
abandoned 2026-08-01: every nba.com host (stats. and cdn. alike) answers
an Akamai "Access Denied" — verified from the Oracle production host *and*
from a residential connection, with and without browser-shaped headers.
The Phase 4 hypothesis that a non-cloud IP would get through is disproved,
so there is no network this app runs on where that endpoint works. Sync now
uses ESPN's scoreboard, which SP3_data_sources.md already designates as
NBA's backup update source, and which additionally carries venue data that
scoreboardv2 never returned.

ESPN cannot supply the NBA's own 8-char gameId, so synced rows cannot share
`source_game_id` with the bulk import. `_find_by_natural_key` reconciles the
two on (league, home, away, start +/- NATURAL_KEY_WINDOW) so that
re-downloading Games.csv later updates the synced row instead of duplicating
it. That window is deliberately narrow and the match must be unique — the
same two teams meet on consecutive nights often enough that a wider one
would overwrite one real game with another.

Team identity: NBA's numeric team id is stable across every relocation/
rename in league history (id 1610612760 is both the Seattle SuperSonics
and the OKC Thunder) — unlike NFL/MLB's era-coded team abbreviations.
We still split each (id, city, name) combo the CSV actually shows into
its own team row for historical accuracy (a 1970 game should say
"Seattle SuperSonics", not "Thunder"), linked by franchise_id = the
numeric team id itself.

Season: derived from the NBA's own gameId encoding (digit 0 = game
type, digits 1-2 = season start year's last two digits), not the game
date — the 2019-20 season's COVID-delayed playoffs ran into October
2020, so date-based inference misclassifies those games; the ID does
not. Safe through 2045 given this dataset's 1946 floor (see `_season`).

Venue caveat: Games.csv only carries arena/city/state/attendance for the
dataset's most recent season as of this writing (the dataset's own
description says older entries are being backfilled by its maintainer
over time) — historical rows arrive with no arena data at all. For those,
`_upsert_row` falls back to the hand-built `sports_passport/data/seed/nba_arenas.csv`
(team → arena → season range, 1990-present); older-still games remain
venue_id = NULL.
"""
import asyncio
import csv
import logging
import os
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Optional

import httpx

from sports_passport.core.config import settings
from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.services.adapters import venue_seed
from sports_passport.services.adapters.base import LeagueAdapter, ImportResult
from sports_passport.services.importer import get_league, upsert_team, upsert_venue, upsert_game

logger = logging.getLogger(__name__)

GAME_TYPES = {
    "Regular Season": "regular",
    "Playoffs": "postseason",
    "Play-in Tournament": "postseason",
    "Preseason": "preseason",
    # In-season tournament group-stage games count toward the 82-game
    # regular season and standings, so they're "regular". The one-off
    # championship final (gameId prefix "6") does not count toward any
    # team's record, so it gets its own type rather than inflating the
    # regular-season count — see the 2023-24 1,231-vs-1,230 mismatch.
    "NBA Emirates Cup": "regular",
    "Emirates NBA Cup": "cup_final",
    "NBA Cup": "cup_final",
    # "All-Star Game" intentionally excluded: uses synthetic non-franchise team ids
}

# Real per-game tip-off times only start showing variety in the CSV from
# 1969 on; earlier seasons carry a single placeholder time for every game.
FIRST_SEASON_WITH_REAL_TIMES = 1969

ONE_DAY = timedelta(days=1)

ESPN_HEADERS = {
    "User-Agent": "SportsPassport/0.2 (personal game-attendance tracker)",
    "Accept": "application/json",
}

# ESPN's season.type on the NBA scoreboard. Anything else (4 = off-season /
# All-Star) is not a countable game and is skipped.
ESPN_SEASON_TYPES = {1: "preseason", 2: "regular", 3: "postseason"}

# Polite spacing between ESPN scoreboard calls; a sync window is a handful of days.
ESPN_THROTTLE_SECONDS = 0.5

# How far apart the same game may look between the two sources. ESPN stamps
# UTC; the Kaggle rows carry a naive *local* tip-off, so the same game differs
# by the venue's UTC offset — at most 8h for a 7:30pm Pacific start.
#
# The ceiling is set by how close two *different* games with the same matchup
# can be. They are not rare: the same pair meets on consecutive nights 294
# times in this dataset (287 of them exactly 24.0h apart, tightest genuine
# modern gap 22h), so an earlier ±1 day window sat exactly on top of them.
# 12h clears the 8h skew and stays well inside the 22h separation.
NATURAL_KEY_WINDOW = timedelta(hours=12)


def _season_from_game_id(game_id: str) -> int:
    """2000+D for D<=45, else 1900+D — see module docstring."""
    d = int(game_id[1:3])
    return 2000 + d if d <= 45 else 1900 + d


def _team_key(team_id: str, city: str, name: str) -> str:
    return f"{team_id}:{city}:{name}"


def _int_or_none(value) -> Optional[int]:
    """ESPN reports scores as strings, and as '' for a game not yet played."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class NbaAdapter(LeagueAdapter):
    league_code = "NBA"
    source = "nba-kaggle"

    http_client_kwargs = {"headers": ESPN_HEADERS, "follow_redirects": True}

    def _read_games_csv(self) -> list[dict]:
        path = os.path.join(settings.data_dir, "raw", "nba", "Games.csv")
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"NBA historical data file not found at {path}. Download "
                "eoinamoore's \"NBA Dataset: Box Scores and Stats\" from Kaggle "
                "and place Games.csv there (see this module's docstring)."
            )
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    async def import_teams(self) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)
        rows = self._read_games_csv()

        seasons_by_key: dict[str, set] = {}
        franchise_seasons: dict[str, set] = {}
        for row in rows:
            if row["gameType"] not in GAME_TYPES:
                continue
            season = _season_from_game_id(row["gameId"])
            for side in ("home", "away"):
                team_id = row[f"{side}teamId"]
                city = row[f"{side}teamCity"]
                name = row[f"{side}teamName"]
                key = _team_key(team_id, city, name)
                seasons_by_key.setdefault(key, set()).add(season)
                franchise_seasons.setdefault(team_id, set()).add(season)

        for key, seasons in seasons_by_key.items():
            team_id, city, name = key.split(":", 2)
            last = max(seasons)
            franchise_last = max(franchise_seasons[team_id])
            _, created = upsert_team(
                self.db,
                source=self.source,
                source_team_id=key,
                league_id=league.id,
                name=f"{city} {name}".strip(),
                nickname=name,
                city=city or None,
                franchise_id=int(team_id),
                first_season=min(seasons),
                last_season=None if last == franchise_last else last,
            )
            if created:
                result.teams_imported += 1

        self.db.commit()
        return result

    def _team_lookup(self, league_id: int) -> dict[str, int]:
        teams = self.db.query(Team).filter(Team.league_id == league_id).all()
        return {t.source_team_id: t.id for t in teams}

    def _upsert_row(self, league_id: int, row: dict, by_key: dict, venue_cache: dict,
                    result: ImportResult, synced_index: Optional[dict] = None) -> None:
        game_type = row["gameType"]
        season_type = GAME_TYPES.get(game_type)
        if season_type is None:
            return

        home_key = _team_key(row["hometeamId"], row["hometeamCity"], row["hometeamName"])
        away_key = _team_key(row["awayteamId"], row["awayteamCity"], row["awayteamName"])
        home_id = by_key.get(home_key)
        away_id = by_key.get(away_key)
        if home_id is None or away_id is None:
            result.errors.append(f"game {row['gameId']}: unmatched team {away_key} @ {home_key}")
            return

        try:
            start_date = datetime.strptime(row["gameDate"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            result.errors.append(f"game {row['gameId']}: bad date {row['gameDate']!r}")
            return

        season = _season_from_game_id(row["gameId"])

        venue_id = None
        arena_name = row.get("arenaName")
        if arena_name:
            venue_id = venue_cache.get(arena_name)
            if venue_id is None:
                venue, created = upsert_venue(
                    self.db,
                    source=self.source,
                    source_venue_id=row.get("arenaId") or arena_name,
                    name=arena_name,
                    city=row.get("arenaCity") or None,
                    state=row.get("arenaState") or None,
                )
                venue_id = venue.id
                venue_cache[arena_name] = venue_id
                if created:
                    result.venues_imported += 1
        else:
            # Games.csv only carries arena data for its most recent season (see
            # module docstring) — for everything older, fall back to the hand-built
            # team -> arena seed (sports_passport/data/seed/nba_arenas.csv, covers 1990-present).
            seed = venue_seed.lookup_nba_arena(row["hometeamId"], season)
            if seed:
                cache_key = f"seed:{seed['arena']}"
                venue_id = venue_cache.get(cache_key)
                if venue_id is None:
                    venue, created = upsert_venue(
                        self.db,
                        source=self.source,
                        source_venue_id=f"seed-{seed['arena']}",
                        name=seed["arena"],
                        **venue_seed.venue_fields(seed),
                    )
                    venue_id = venue.id
                    venue_cache[cache_key] = venue_id
                    if created:
                        result.venues_imported += 1

        attendance = int(row["attendance"]) if row.get("attendance", "").strip().isdigit() else None
        if attendance == 0:
            attendance = None

        # A game ESPN synced before this CSV covered it lives under an
        # "espn-<event id>" source id. Adopt that row rather than inserting a
        # second one for the same game — the NBA gameId is the better key, so
        # it wins, and the natural-key duplicate disappears for good.
        if synced_index:
            self._adopt_synced_row(
                synced_index, league_id, home_id, away_id, start_date, row["gameId"]
            )

        _, created = upsert_game(
            self.db,
            source=self.source,
            source_game_id=row["gameId"],
            league_id=league_id,
            home_team_id=home_id,
            away_team_id=away_id,
            home_score=int(row["homeScore"]),
            away_score=int(row["awayScore"]),
            start_date=start_date,
            has_time=season >= FIRST_SEASON_WITH_REAL_TIMES,
            season=season,
            season_type=season_type,
            venue_id=venue_id,
            neutral_site=False,
            attendance=attendance,
        )
        if created:
            result.games_imported += 1
        else:
            result.games_updated += 1

    async def import_historical(self, start_season: int, end_season: int) -> ImportResult:
        result = ImportResult(league=self.league_code)
        result.merge(await self.import_teams())

        league = get_league(self.db, self.league_code)
        by_key = self._team_lookup(league.id)
        venue_cache: dict[str, int] = {}
        synced_index = self._synced_row_index(league.id)

        rows = self._read_games_csv()
        for row in rows:
            if row["gameType"] not in GAME_TYPES:
                continue
            season = _season_from_game_id(row["gameId"])
            if season < start_season or season > end_season:
                continue
            self._upsert_row(league.id, row, by_key, venue_cache, result, synced_index)

        self.db.commit()
        logger.info("NBA import: %s games imported, %s updated", result.games_imported, result.games_updated)
        return result

    # ------------------------------------------------------------------
    # Sync (ESPN)
    # ------------------------------------------------------------------

    async def _fetch_scoreboard(self, day: date) -> dict:
        response = await self.http.get(
            f"{settings.espn_api_url}/basketball/nba/scoreboard",
            params={"dates": day.strftime("%Y%m%d")},
        )
        response.raise_for_status()
        return response.json()

    def _active_team_by_name(self, league_id: int) -> dict[str, int]:
        """ESPN displayName -> db team id, active era only.

        Sync only ever sees current games, so resolution must land on each
        franchise's present-day identity row rather than an arbitrary
        historical era sharing the same NBA team id (Seattle SuperSonics
        vs. OKC Thunder). Matched on name because the Kaggle bulk import
        leaves `abbreviation` NULL — verified live that all 30 of ESPN's
        displayNames equal our team names exactly.
        """
        teams = self.db.query(Team).filter(
            Team.league_id == league_id, Team.last_season.is_(None)
        ).all()
        return {t.name: t.id for t in teams}

    def _synced_row_index(self, league_id: int) -> dict[tuple, list[Game]]:
        """Every ESPN-synced row for this league, grouped by matchup.

        Built once per import: a full backfill calls the adoption check 73k+
        times, and a per-row query against a column with no selective index
        turned that into roughly twelve minutes of pure lookup. There are only
        ever a handful of espn- rows (one sync window's worth), so holding them
        in memory costs nothing.
        """
        synced = self.db.query(Game).filter(
            Game.league_id == league_id,
            Game.source == self.source,
            Game.source_game_id.like("espn-%"),
        ).all()
        index: dict[tuple, list[Game]] = {}
        for game in synced:
            index.setdefault((game.home_team_id, game.away_team_id), []).append(game)
        return index

    def _adopt_synced_row(
        self, index: dict, league_id: int, home_id: int, away_id: int,
        start: datetime, game_id: str,
    ) -> None:
        """Re-key an ESPN-synced row onto its real NBA gameId, if one exists.

        Only touches rows this adapter synced (source id prefixed "espn-"),
        never adopts when the canonical id is already present, and refuses to
        choose between two candidates -- so it cannot merge two legitimately
        distinct games. Consecutive-night repeat matchups make that last guard
        load-bearing, not theoretical.
        """
        bucket = index.get((home_id, away_id))
        if not bucket:
            return
        candidates = [
            g for g in bucket
            if abs(g.start_date - start) <= NATURAL_KEY_WINDOW
        ]
        if len(candidates) != 1:
            return

        already = self.db.query(Game).filter(
            Game.source == self.source,
            Game.source_game_id == game_id,
        ).first()
        if already:
            return

        adopted = candidates[0]
        adopted.source_game_id = game_id
        bucket.remove(adopted)          # never adopt the same row twice
        self.db.flush()

    def _candidates_in_window(
        self, league_id: int, home_id: int, away_id: int, start: datetime
    ) -> list[Game]:
        return self.db.query(Game).filter(
            Game.league_id == league_id,
            Game.source == self.source,
            Game.home_team_id == home_id,
            Game.away_team_id == away_id,
            Game.start_date >= start - NATURAL_KEY_WINDOW,
            Game.start_date <= start + NATURAL_KEY_WINDOW,
        ).all()

    def _find_by_natural_key(
        self, league_id: int, home_id: int, away_id: int, start: datetime
    ) -> tuple[Optional[Game], bool]:
        """The existing row for this matchup. Returns (game, ambiguous).

        ESPN cannot supply the NBA's own 8-char gameId, so a synced row and
        the Kaggle bulk row for the same game have different source ids and
        would otherwise coexist as duplicates. Matching on
        (league, home, away, start +/- NATURAL_KEY_WINDOW) lets them converge.

        Two candidates inside the window means the window is doing something
        it cannot do safely, so the caller is told rather than handed a guess:
        picking the wrong one silently rewrites a real game's date and score,
        and would drag any attendance record along with it.
        """
        candidates = self._candidates_in_window(league_id, home_id, away_id, start)
        if not candidates:
            return None, False
        if len(candidates) > 1:
            return None, True
        return candidates[0], False

    async def sync_recent(self, since: date) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)
        by_name = self._active_team_by_name(league.id)
        venue_cache: dict[str, int] = {}
        skips: Counter = Counter()

        day = since
        today = date.today()
        first = True
        while day <= today:
            if not first:
                await asyncio.sleep(ESPN_THROTTLE_SECONDS)
            first = False
            try:
                payload = await self._fetch_scoreboard(day)
            except (httpx.HTTPError, ValueError) as e:
                result.errors.append(f"{day.isoformat()}: fetch failed ({e!r})")
                day += ONE_DAY
                continue

            for event in payload.get("events", []):
                self._upsert_espn_event(league.id, event, by_name, venue_cache, result, skips)
            day += ONE_DAY

        self.db.commit()
        for reason, count in skips.items():
            logger.info("NBA sync: skipped %s event(s) — %s", count, reason)
        return result

    def _espn_venue_id(
        self, competition: dict, home_franchise_id: Optional[str], season: int,
        venue_cache: dict, result: ImportResult,
    ) -> Optional[int]:
        """Resolve the arena, preferring the seed so rows stay deduplicated.

        The seed (team + season era) is the same lookup the bulk import and
        scripts/backfill_venue_seeds.py use, so a synced game lands on the
        existing venue row -- with the hand-verified coordinates the map needs
        -- instead of minting a second row for the same building. ESPN's own
        venue is the fallback, and the only option for neutral-site games,
        where the home team's usual arena would be plain wrong.
        """
        neutral = bool(competition.get("neutralSite"))
        seed = None
        if not neutral and home_franchise_id:
            seed = venue_seed.lookup_nba_arena(home_franchise_id, season)

        if seed:
            key = f"seed-{seed['arena']}"
            if key not in venue_cache:
                venue, created = upsert_venue(
                    self.db, source=self.source, source_venue_id=key,
                    name=seed["arena"], **venue_seed.venue_fields(seed),
                )
                self.db.flush()
                venue_cache[key] = venue.id
                if created:
                    result.venues_imported += 1
            return venue_cache[key]

        espn_venue = competition.get("venue") or {}
        if not espn_venue.get("fullName"):
            return None
        key = f"espn-{espn_venue.get('id') or espn_venue['fullName']}"
        if key not in venue_cache:
            address = espn_venue.get("address") or {}
            venue, created = upsert_venue(
                self.db, source=self.source, source_venue_id=key,
                name=espn_venue["fullName"],
                city=address.get("city"), state=address.get("state"), country=None,
            )
            self.db.flush()
            venue_cache[key] = venue.id
            if created:
                result.venues_imported += 1
        return venue_cache[key]

    def _upsert_espn_event(
        self, league_id: int, event: dict, by_name: dict, venue_cache: dict,
        result: ImportResult, skips: Counter,
    ) -> bool:
        """Returns False when the event was skipped (not an error).

        Skips are counted by reason rather than lumped together: the expected
        one is All-Star weekend, whose squads ("Team Stars", "Team Stripes",
        "World") are not franchises and are excluded from the bulk import too.
        Reporting them all as one number would let a genuine regression -- ESPN
        renaming a team, or the NBA teams never having been imported on this
        host -- sit behind a green nightly status forever.
        """
        competitions = event.get("competitions") or []
        if not competitions:
            skips["no competition"] += 1
            return False
        competition = competitions[0]

        season_info = event.get("season") or {}
        season_type = ESPN_SEASON_TYPES.get(season_info.get("type"))
        if not season_type:
            skips[f"season type {season_info.get('type')!r}"] += 1
            return False
        # ESPN labels a season by its ending year (2025-26 -> 2026); this app
        # keys seasons by the starting year, matching the NBA gameId encoding
        # the bulk import derives its season from.
        espn_year = season_info.get("year")
        if not espn_year:
            skips["no season year"] += 1
            return False
        season = int(espn_year) - 1

        home = away = None
        for competitor in competition.get("competitors", []):
            if competitor.get("homeAway") == "home":
                home = competitor
            elif competitor.get("homeAway") == "away":
                away = competitor
        if not home or not away:
            skips["missing competitor"] += 1
            return False

        home_id = by_name.get((home.get("team") or {}).get("displayName"))
        away_id = by_name.get((away.get("team") or {}).get("displayName"))
        if home_id is None or away_id is None:
            unknown = [
                (c.get("team") or {}).get("displayName")
                for c, resolved in ((home, home_id), (away, away_id)) if resolved is None
            ]
            skips[f"unknown team(s): {', '.join(str(u) for u in unknown)}"] += 1
            return False

        try:
            start_date = datetime.strptime(event["date"], "%Y-%m-%dT%H:%MZ")
        except (KeyError, ValueError):
            result.errors.append(f"event {event.get('id')}: bad date {event.get('date')!r}")
            return True

        # Gate on `completed`, not on state != "pre". A postponed or canceled
        # game comes back with state "post" and score "0", so a state-based
        # check would write a phantom 0-0 final -- and overwrite a real score
        # with it if the game had already been played and later corrected.
        status_type = (competition.get("status") or {}).get("type") or {}
        if status_type.get("completed"):
            home_score = _int_or_none(home.get("score"))
            away_score = _int_or_none(away.get("score"))
        else:
            home_score = away_score = None

        home_franchise = self.db.get(Team, home_id)
        venue_id = self._espn_venue_id(
            competition,
            str(home_franchise.franchise_id) if home_franchise and home_franchise.franchise_id else None,
            season, venue_cache, result,
        )

        fields = dict(
            home_team_id=home_id,
            away_team_id=away_id,
            home_score=home_score,
            away_score=away_score,
            start_date=start_date,
            has_time=True,
            season=season,
            season_type=season_type,
            venue_id=venue_id,
            neutral_site=bool(competition.get("neutralSite")),
        )

        existing, ambiguous = self._find_by_natural_key(league_id, home_id, away_id, start_date)
        if ambiguous:
            result.errors.append(
                f"event {event.get('id')}: {start_date.isoformat()} matches more than one "
                "existing game for this matchup; refusing to guess"
            )
            return True
        if existing:
            for key, value in fields.items():
                # Never blank an already-known score with a not-yet-played null.
                if value is None and key in ("home_score", "away_score", "venue_id"):
                    continue
                # The bulk import splits the in-season tournament final out as
                # its own type because it counts toward nobody's record. ESPN
                # reports it as an ordinary regular-season game, so let the
                # more specific classification stand rather than flattening it.
                if key == "season_type" and existing.season_type == "cup_final" and value == "regular":
                    continue
                setattr(existing, key, value)
            result.games_updated += 1
            return True

        upsert_game(
            self.db,
            source=self.source,
            source_game_id=f"espn-{event['id']}",
            league_id=league_id,
            **fields,
        )
        result.games_imported += 1
        return True
