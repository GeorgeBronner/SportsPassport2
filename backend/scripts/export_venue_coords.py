"""Export building-level venue coordinates to the committed seed CSV.

Run this after `geocode_venues.py` has placed venues in a development
database. The CSV it writes is what staging and production consume via
`scripts/load_venue_coords.py`, so they never have to repeat the ~3,500
throttled Nominatim requests a full geocoding pass costs.

Venues still sitting on a city centroid are excluded — that value carries no
information the target database can't derive itself, and exporting it would
overwrite a better coordinate that environment might already hold. Whether a
coordinate *is* a centroid is decided the same way `geocode_venues.py` decides
it: by looking the value up among the cities in the geocode cache.

Usage (from backend/):
    uv run python scripts/export_venue_coords.py
    uv run python scripts/export_venue_coords.py --dry-run
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geocode_venues import city_centroids, load_cache  # noqa: E402

from sports_passport.db.database import SessionLocal  # noqa: E402
from sports_passport.models import Venue  # noqa: E402
from sports_passport.services.venue_coords import COORDS_PATH, FIELDNAMES  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Export venue coordinates")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args()

    centroids = city_centroids(load_cache())

    with SessionLocal() as db:
        rows = []
        skipped = 0
        query = db.query(Venue).filter(
            Venue.latitude.isnot(None),
            Venue.longitude.isnot(None),
            Venue.source.isnot(None),
            Venue.source_venue_id.isnot(None),
        )
        for v in query.order_by(Venue.source, Venue.source_venue_id):
            if v.latitude is None or v.longitude is None:
                continue
            if (round(v.latitude, 5), round(v.longitude, 5)) in centroids:
                skipped += 1  # city fallback — nothing worth shipping
                continue
            rows.append(
                {
                    "source": v.source,
                    "source_venue_id": v.source_venue_id,
                    "name": v.name,
                    "latitude": f"{v.latitude:.6f}",
                    "longitude": f"{v.longitude:.6f}",
                }
            )

    print(f"{len(rows)} building-level venue(s) · {skipped} on a city centroid (excluded)")
    if args.dry_run:
        for r in rows[:10]:
            print(f"  {r['source']}:{r['source_venue_id']} {r['name']} "
                  f"{r['latitude']},{r['longitude']}")
        return

    COORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    # newline="" per csv docs, and \n explicitly so the committed file does not
    # change shape depending on which OS exported it.
    with COORDS_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {COORDS_PATH}")


if __name__ == "__main__":
    main()
