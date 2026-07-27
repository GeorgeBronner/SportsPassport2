"""Hand-built venue location lookups for leagues whose live source doesn't
carry city/state (NFL, NHL) or is historically sparse for venue info (NBA,
pre-current-season) — see backend/data/seed/*.csv. Coordinates are supplied
directly (arena/stadium-level precision) rather than routing through
scripts/geocode_venues.py, since these are small, finite, hand-verified lists.
"""
import csv
import os
from functools import lru_cache
from typing import Optional

from sports_passport.core.config import settings


def _seed_path(filename: str) -> str:
    return os.path.join(settings.data_dir, "seed", filename)


@lru_cache(maxsize=1)
def nfl_stadiums() -> dict[str, dict]:
    """nflverse stadium_id -> seed row."""
    with open(_seed_path("nfl_stadiums.csv"), newline="", encoding="utf-8") as f:
        return {row["stadium_id"]: row for row in csv.DictReader(f)}


@lru_cache(maxsize=1)
def nhl_arenas() -> dict[str, dict]:
    """NHL API venue name -> seed row (the API exposes no stable venue id)."""
    with open(_seed_path("nhl_arenas.csv"), newline="", encoding="utf-8") as f:
        return {row["name"]: row for row in csv.DictReader(f)}


@lru_cache(maxsize=1)
def _nba_arenas_by_team() -> dict[str, list[dict]]:
    by_team: dict[str, list[dict]] = {}
    with open(_seed_path("nba_arenas.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_team.setdefault(row["team_id"], []).append(row)
    return by_team


def lookup_nba_arena(team_id: str, season: int) -> Optional[dict]:
    """The seed row whose [start_season, end_season] covers this season, if any."""
    for row in _nba_arenas_by_team().get(str(team_id), []):
        start = int(row["start_season"])
        end = int(row["end_season"]) if row["end_season"] else None
        if season >= start and (end is None or season <= end):
            return row
    return None


def venue_fields(row: dict) -> dict:
    """city/state/country/latitude/longitude kwargs for upsert_venue, blanks as None."""
    return {
        "city": row.get("city") or None,
        "state": row.get("state") or None,
        "country": row.get("country") or None,
        "latitude": float(row["latitude"]) if row.get("latitude") else None,
        "longitude": float(row["longitude"]) if row.get("longitude") else None,
    }
