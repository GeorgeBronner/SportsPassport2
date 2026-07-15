"""Backfill venues.latitude/longitude by geocoding city/state.

City-level precision is all the venue map needs, so venues are geocoded by
their city+state through Nominatim (OpenStreetMap) at the polite 1 req/sec,
with a persistent city->coords cache so re-runs and shared cities cost nothing.

By default only venues someone has attended a game at are geocoded (fast, ~40
lookups). Use --all for the full venue table (~2k venues; takes ~30 min cold).

Usage (from backend/):
    uv run python scripts/geocode_venues.py            # attended venues only
    uv run python scripts/geocode_venues.py --all
    uv run python scripts/geocode_venues.py --dry-run
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports_passport.db.database import SessionLocal  # noqa: E402
from sports_passport.models import Venue, Game, UserGameAttendance  # noqa: E402

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "SportsPassport/0.2 (personal game-attendance tracker; venue geocoding)"}
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "geocode_cache.json"
THROTTLE_SECONDS = 1.1  # Nominatim usage policy: max 1 request/second

# State values appear both as codes ('AL') and full names ('Alabama') in the
# venues table depending on source; Nominatim handles either in a q= search.


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")


def geocode_city(client: httpx.Client, cache: dict, city: str, state: str, country: str) -> tuple | None:
    key = f"{city}|{state}|{country}".lower()
    if key in cache:
        return tuple(cache[key]) if cache[key] else None

    resp = client.get(
        NOMINATIM_URL,
        params={"q": f"{city}, {state}, {country}", "format": "json", "limit": 1},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    hits = resp.json()
    coords = (float(hits[0]["lat"]), float(hits[0]["lon"])) if hits else None
    cache[key] = list(coords) if coords else None
    save_cache(cache)
    time.sleep(THROTTLE_SECONDS)
    return coords


def main():
    parser = argparse.ArgumentParser(description="Geocode venue cities")
    parser.add_argument("--all", action="store_true", help="geocode every venue, not just attended ones")
    parser.add_argument("--dry-run", action="store_true", help="report what would be geocoded")
    args = parser.parse_args()

    with SessionLocal() as db:
        query = db.query(Venue).filter(
            Venue.latitude.is_(None),
            Venue.city.isnot(None),
        )
        if not args.all:
            attended_venue_ids = (
                db.query(Game.venue_id)
                .join(UserGameAttendance, UserGameAttendance.game_id == Game.id)
                .filter(Game.venue_id.isnot(None))
                .distinct()
            )
            query = query.filter(Venue.id.in_(attended_venue_ids))
        venues = query.all()
        print(f"{len(venues)} venue(s) need coordinates")
        if args.dry_run:
            for v in venues:
                print(f"  {v.name} — {v.city}, {v.state}")
            return

        cache = load_cache()
        done = missed = 0
        with httpx.Client() as client:
            for v in venues:
                coords = geocode_city(client, cache, v.city, v.state or "", v.country or "USA")
                if coords:
                    v.latitude, v.longitude = coords
                    done += 1
                else:
                    missed += 1
                    print(f"  no result: {v.name} — {v.city}, {v.state}")
        db.commit()
        print(f"geocoded {done} · unresolved {missed}")


if __name__ == "__main__":
    main()
