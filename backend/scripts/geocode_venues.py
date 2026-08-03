"""Backfill venues.latitude/longitude by geocoding the venue itself.

Venues are geocoded by *name* + city/state through Nominatim (OpenStreetMap)
at the polite 1 req/sec, falling back to the city centroid when the building
can't be resolved. A persistent cache keyed by both tiers makes re-runs free.

This used to geocode by city+state alone, on the reasoning that city-level
precision was all the venue map needed. That held while the map was a fixed
continental overview; it stopped holding when the map learned to zoom, because
every venue in a city landed on one point. Five New York grounds — both Yankee
Stadiums, Citi Field, and a Madison Square Garden row — sat on top of each
other at City Hall, and Chicago and Atlanta had the same pile.

Two guards keep a re-run from making things worse:

* Only NULL coordinates and coordinates that *are* a known city centroid get
  touched. Venues placed by a source that publishes real coordinates (the ASA
  API) or by the hand-verified seed CSVs are already building-precise, and are
  left alone.
* A venue-level hit more than MAX_DRIFT_KM from its city is rejected as a
  mis-match and falls back to the centroid. Nominatim will happily answer
  "Memorial Stadium" with one in the wrong state.

Usage (from backend/):
    uv run python scripts/geocode_venues.py            # attended venues only
    uv run python scripts/geocode_venues.py --all
    uv run python scripts/geocode_venues.py --dry-run
"""

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports_passport.db.database import SessionLocal  # noqa: E402
from sports_passport.models import Game, UserGameAttendance, Venue  # noqa: E402

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "SportsPassport/0.2 (personal game-attendance tracker; venue geocoding)"}
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "geocode_cache.json"
THROTTLE_SECONDS = 1.1  # Nominatim usage policy: max 1 request/second

# A stadium can legitimately sit well outside the city it is named for —
# MetLife is 10km from Manhattan, and college grounds sprawl further — but a
# hit hundreds of km away is a different building with the same name.
MAX_DRIFT_KM = 100.0

# Retrosheet distinguishes successive grounds on one site with a trailing
# numeral ("Yankee Stadium II"), which no gazetteer knows. Parenthetical
# qualifiers are similarly ours, not OSM's.
NAME_NOISE = re.compile(r"\s*\((?:[^)]*)\)|\s+(?:I{1,3}|IV|V)$")

# Buildings OSM files under a different name than our sources use: a
# naming-rights era we didn't follow, an abbreviation of ours, or a ground
# that no longer exists. Hand-verified and deliberately tiny — the same
# posture as the seed CSVs, and the last resort after the query tiers below.
# The Georgia Dome was demolished in 2017; its successor stands ~200m away on
# the adjacent site, which is the convention venue_seed.py already uses for
# demolished grounds.
NAME_ALIASES = {
    "dkr-texas memorial stadium": "Darrell K Royal-Texas Memorial Stadium",
    "georgia dome": "Mercedes-Benz Stadium",
    "high point solutions stadium": "SHI Stadium",
    "kroger field": "Commonwealth Stadium",
}

# State values appear both as codes ('AL') and full names ('Alabama') in the
# venues table depending on source; Nominatim handles either in a q= search.


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")


def haversine_km(a: tuple, b: tuple) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def lookup(client: httpx.Client, cache: dict, key: str, query: str) -> tuple | None:
    """One cached, throttled Nominatim search. A cached null is a real answer."""
    if key in cache:
        return tuple(cache[key]) if cache[key] else None

    resp = client.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
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


def geocode_city(client: httpx.Client, cache: dict, city: str, state: str, country: str):
    return lookup(
        client, cache, f"{city}|{state}|{country}".lower(), f"{city}, {state}, {country}"
    )


def geocode_venue(
    client: httpx.Client, cache: dict, name: str, city: str, state: str, country: str
) -> tuple:
    """Best coordinates for one venue, plus how they were found.

    Each name candidate — the alias if we have one, the name as stored, the
    name with our own suffixes stripped — is tried against the city and then
    against the state alone. The state tier matters more than it looks: our
    `city` is the postal town, and OSM often files a ground under a different
    one (Michie Stadium is at West Point, which OSM calls Town of Highlands),
    so dropping the city is what resolves those rather than any alias.

    Every candidate must land within MAX_DRIFT_KM of the city, which is what
    makes the city lookup worth doing first — it is the yardstick, and the
    fallback when nothing better survives.
    """
    centroid = geocode_city(client, cache, city, state, country)

    candidates: list[str] = []
    alias = NAME_ALIASES.get(name.strip().lower())
    if alias:
        candidates.append(alias)
    if name:
        candidates.append(name)
        cleaned = NAME_NOISE.sub("", name).strip()
        if cleaned:
            candidates.append(cleaned)

    seen: set[str] = set()
    for candidate in candidates:
        if candidate.lower() in seen:
            continue
        seen.add(candidate.lower())
        for scope in (city, ""):
            place = ", ".join(p for p in (candidate, scope, state, country) if p)
            coords = lookup(client, cache, f"venue|{place}".lower(), place)
            if not coords:
                continue
            if centroid and haversine_km(coords, centroid) > MAX_DRIFT_KM:
                # Same name, wrong building — the state tier especially will
                # answer with one three states over. Keep looking.
                continue
            return coords, "venue"

    return centroid, "city" if centroid else "unresolved"


def city_centroids(cache: dict) -> set:
    """Rounded coordinates of every city we have ever geocoded."""
    return {
        (round(v[0], 5), round(v[1], 5))
        for k, v in cache.items()
        if v and not k.startswith("venue|")
    }


def main():
    parser = argparse.ArgumentParser(description="Geocode venues")
    parser.add_argument(
        "--all", action="store_true", help="geocode every venue, not just attended ones"
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would be geocoded")
    args = parser.parse_args()

    cache = load_cache()
    centroids = city_centroids(cache)

    with SessionLocal() as db:
        query = db.query(Venue).filter(Venue.city.isnot(None))
        if not args.all:
            attended_venue_ids = (
                db.query(Game.venue_id)
                .join(UserGameAttendance, UserGameAttendance.game_id == Game.id)
                .filter(Game.venue_id.isnot(None))
                .distinct()
            )
            query = query.filter(Venue.id.in_(attended_venue_ids))

        def needs_placing(v: Venue) -> bool:
            # Anything else already has building-level coordinates from a
            # source that publishes them, or from a hand-verified seed CSV.
            if v.latitude is None or v.longitude is None:
                return True
            return (round(v.latitude, 5), round(v.longitude, 5)) in centroids

        venues = [v for v in query.all() if needs_placing(v)]
        print(f"{len(venues)} venue(s) to place")
        if args.dry_run:
            for v in venues:
                where = "no coords" if v.latitude is None else "city centroid"
                print(f"  [{where}] {v.name} — {v.city}, {v.state}")
            return

        placed = fallback = missed = 0
        with httpx.Client() as client:
            for v in venues:
                coords, how = geocode_venue(
                    client, cache, v.name or "", v.city or "", v.state or "", v.country or "USA"
                )
                if coords:
                    v.latitude, v.longitude = coords
                if how == "venue":
                    placed += 1
                elif how == "city":
                    fallback += 1
                    print(f"  city-level only: {v.name} — {v.city}, {v.state}")
                else:
                    missed += 1
                    print(f"  no result: {v.name} — {v.city}, {v.state}")
        db.commit()
        print(f"venue-level {placed} · city fallback {fallback} · unresolved {missed}")


if __name__ == "__main__":
    main()
