"""Apply the committed venue coordinates to this database.

The counterpart to `export_venue_coords.py`, and what staging and production
run instead of geocoding for themselves. Reads
`sports_passport/data/seed/venue_coordinates.csv` from inside the package —
never from the data volume, which the Docker bind-mount would shadow.

Matching is on `(source, source_venue_id)`, so it does not matter that
`venues.id` differs between databases. Venues in the file that this database
doesn't have are reported, not treated as failures: environments legitimately
differ in which imports they have run.

Safe to re-run — a second pass reports everything as unchanged.

Usage (from backend/, or in the container as `python scripts/...`):
    uv run python scripts/load_venue_coords.py --dry-run
    uv run python scripts/load_venue_coords.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports_passport.db.database import SessionLocal  # noqa: E402
from sports_passport.services.venue_coords import (  # noqa: E402
    COORDS_PATH,
    apply_venue_coordinates,
    venue_coordinates,
)


def main():
    parser = argparse.ArgumentParser(description="Apply committed venue coordinates")
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would change, write nothing"
    )
    args = parser.parse_args()

    coords = venue_coordinates()
    if not coords:
        # Exit non-zero: an empty file almost certainly means the CSV did not
        # make it into the image, and silence would read as success.
        print(f"no coordinates found at {COORDS_PATH}", file=sys.stderr)
        return 1
    print(f"{len(coords)} coordinate(s) in {COORDS_PATH.name}")

    with SessionLocal() as db:
        result = apply_venue_coordinates(db, dry_run=args.dry_run)

    verb = "would update" if args.dry_run else "updated"
    print(f"{verb} {result.updated} · unchanged {result.unchanged} · not in this database "
          f"{result.missing}")
    if result.missing_examples:
        shown = ", ".join(result.missing_examples)
        more = "" if result.missing <= len(result.missing_examples) else ", ..."
        print(f"  missing e.g.: {shown}{more}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
