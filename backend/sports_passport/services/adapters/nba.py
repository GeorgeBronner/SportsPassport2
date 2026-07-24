"""NBA adapter — Kaggle bulk CSV (historical) + stats.nba.com (sync).

stats.nba.com is unreachable in dev (hangs on an Akamai anti-bot TLS
challenge, not just a rate limit — confirmed 2026-07-11), and its
documented fallback, a Kaggle bulk CSV, needs a Kaggle login same as the
NFL Spreadspoke dataset. The user grabbed it manually (free account, no
payment) — see backend/data/raw/nba/Games.csv (eoinamoore's "NBA Dataset:
Box Scores and Stats" on Kaggle). Unlike the other four adapters,
`import_historical` therefore parses a local file rather than fetching
live; there's no other free live bulk source to fall back to.

`sync_recent` still targets stats.nba.com's `scoreboardv2` endpoint per
the original plan (small "since date" queries are exactly its intended
free use) — implemented but **not live-verified**, since this dev
environment can't reach it at all. A home/production network may well
succeed where this sandbox's egress is blocked; verify after deploy.

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
over time) — historical games import with venue_id = NULL. A hand-built
`data/seed/nba_arenas.csv` (team → arena → season range) is the planned
fix, per SP3_plan.md Phase 4; not yet built.
"""
import csv
import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional

import httpx

from sports_passport.core.config import settings
from sports_passport.models.team import Team
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

NBA_STATS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
}


def _season_from_game_id(game_id: str) -> int:
    """2000+D for D<=45, else 1900+D — see module docstring."""
    d = int(game_id[1:3])
    return 2000 + d if d <= 45 else 1900 + d


def _team_key(team_id: str, city: str, name: str) -> str:
    return f"{team_id}:{city}:{name}"


class NbaAdapter(LeagueAdapter):
    league_code = "NBA"
    source = "nba-kaggle"

    http_client_kwargs = {"headers": NBA_STATS_HEADERS, "follow_redirects": True}

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

    def _upsert_row(self, league_id: int, row: dict, by_key: dict, venue_cache: dict, result: ImportResult) -> None:
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

        attendance = int(row["attendance"]) if row.get("attendance", "").strip().isdigit() else None
        if attendance == 0:
            attendance = None

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

        rows = self._read_games_csv()
        for row in rows:
            if row["gameType"] not in GAME_TYPES:
                continue
            season = _season_from_game_id(row["gameId"])
            if season < start_season or season > end_season:
                continue
            self._upsert_row(league.id, row, by_key, venue_cache, result)

        self.db.commit()
        logger.info("NBA import: %s games imported, %s updated", result.games_imported, result.games_updated)
        return result

    async def _fetch_scoreboard(self, day: date) -> dict:
        response = await self.http.get(
            f"{settings.nba_stats_api_url}/scoreboardv2",
            params={"GameDate": day.strftime("%m/%d/%Y"), "LeagueID": "00", "DayOffset": 0},
        )
        response.raise_for_status()
        return response.json()

    def _active_team_lookup(self, league_id: int) -> dict[str, int]:
        """franchise_id (== NBA's numeric team id) -> db id, active era only.

        Sync only ever deals with recent/current games, so resolution must
        land on each franchise's *current* identity row, not an arbitrary
        historical era sharing the same team id (e.g. Seattle SuperSonics
        vs. OKC Thunder).
        """
        teams = self.db.query(Team).filter(Team.league_id == league_id, Team.last_season.is_(None)).all()
        return {str(t.franchise_id): t.id for t in teams}

    async def sync_recent(self, since: date) -> ImportResult:
        result = ImportResult(league=self.league_code)
        league = get_league(self.db, self.league_code)
        active_by_team_id = self._active_team_lookup(league.id)

        day = since
        today = date.today()
        while day <= today:
            try:
                payload = await self._fetch_scoreboard(day)
            except httpx.HTTPError as e:
                result.errors.append(f"{day.isoformat()}: fetch failed ({e})")
                day += ONE_DAY
                continue

            result_sets = {rs["name"]: rs for rs in payload.get("resultSets", [])}
            games = result_sets.get("GameHeader")
            lines = result_sets.get("LineScore")
            if games and lines:
                line_by_game_team = {
                    (row[lines["headers"].index("GAME_ID")], row[lines["headers"].index("TEAM_ID")]): row
                    for row in lines["rowSet"]
                }
                headers = games["headers"]
                for row in games["rowSet"]:
                    game = dict(zip(headers, row))
                    self._upsert_scoreboard_game(
                        league.id, game, lines["headers"], line_by_game_team, active_by_team_id, result
                    )

            day += ONE_DAY

        self.db.commit()
        return result

    def _upsert_scoreboard_game(
        self, league_id: int, game: dict, line_headers: list, line_by_game_team: dict,
        active_by_team_id: dict, result: ImportResult,
    ) -> None:
        game_id = game["GAME_ID"]
        # scoreboardv2's GAME_ID is 10 chars ("00" league prefix + the same
        # type/season/game-number digits the Kaggle bulk CSV uses as its
        # 8-char gameId) — strip the prefix so sync rows land on the exact
        # source_game_id the historical import created, and so
        # _season_from_game_id (calibrated for the 8-char form) parses the
        # season digits correctly instead of reading the league prefix.
        kaggle_id = game_id[2:] if len(game_id) == 10 else game_id
        home_line = line_by_game_team.get((game_id, game["HOME_TEAM_ID"]))
        away_line = line_by_game_team.get((game_id, game["VISITOR_TEAM_ID"]))
        if not home_line or not away_line:
            result.errors.append(f"game {game_id}: missing line score")
            return

        def li(row, field):
            return row[line_headers.index(field)]

        home_id = active_by_team_id.get(str(game["HOME_TEAM_ID"]))
        away_id = active_by_team_id.get(str(game["VISITOR_TEAM_ID"]))
        if home_id is None or away_id is None:
            result.errors.append(f"game {game_id}: unmatched team")
            return

        try:
            start_date = datetime.strptime(game["GAME_DATE_EST"][:10], "%Y-%m-%d")
        except (KeyError, ValueError):
            result.errors.append(f"game {game_id}: bad date")
            return

        _, created = upsert_game(
            self.db,
            source=self.source,
            source_game_id=kaggle_id,
            league_id=league_id,
            home_team_id=home_id,
            away_team_id=away_id,
            home_score=li(home_line, "PTS"),
            away_score=li(away_line, "PTS"),
            start_date=start_date,
            has_time=False,
            season=_season_from_game_id(kaggle_id),
            season_type=GAME_TYPES.get("Regular Season"),
            neutral_site=False,
        )
        if created:
            result.games_imported += 1
        else:
            result.games_updated += 1
