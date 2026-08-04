"""Committed venue coordinates, keyed on the venue's natural key.

`scripts/geocode_venues.py` derives coordinates from Nominatim, which costs
one throttled request per lookup — a full pass is ~3,500 requests and well
over an hour. Doing that once per environment would re-derive an identical
answer three times over, so the result is exported here instead and applied
everywhere else from this file.

Keyed on `(source, source_venue_id)` because that is what survives the trip:
`venues.id` is an autoincrement that differs between databases, while the
natural key is the same one `importer.upsert_venue` deduplicates on, so a row
exported from one database finds its counterpart in any other that ran the
same imports.

The CSV lives *inside the package*, not under `settings.data_dir`. `data_dir`
is the Docker bind-mount volume, and the mount shadows whatever the image put
there — the same trap that took the venue seed CSVs down in production once
already (see tests/test_venue_seed.py). Resolving from `__file__` is what
keeps this working from any working directory.

Only building-level coordinates are exported. Venues sitting on a city
centroid are deliberately excluded: that value is a fallback the target
database can derive for itself, and shipping it would overwrite a better
coordinate that environment might already hold.
"""
import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from sports_passport.models.venue import Venue

COORDS_PATH = Path(__file__).resolve().parents[1] / "data" / "seed" / "venue_coordinates.csv"

FIELDNAMES = ("source", "source_venue_id", "name", "latitude", "longitude")


@dataclass
class LoadResult:
    """What `apply_venue_coordinates` did. `missing` is expected, not an error —
    a target database legitimately holds a different set of venues."""

    updated: int = 0
    unchanged: int = 0
    missing: int = 0
    missing_examples: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.missing_examples is None:
            self.missing_examples = []


@lru_cache(maxsize=1)
def venue_coordinates() -> dict[tuple[str, str], tuple[float, float]]:
    """`(source, source_venue_id)` -> `(latitude, longitude)` from the CSV."""
    if not COORDS_PATH.exists():
        return {}
    out: dict[tuple[str, str], tuple[float, float]] = {}
    with COORDS_PATH.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            source = (row.get("source") or "").strip()
            venue_id = (row.get("source_venue_id") or "").strip()
            if not source or not venue_id:
                continue
            try:
                out[(source, venue_id)] = (float(row["latitude"]), float(row["longitude"]))
            except (TypeError, ValueError):
                continue  # a malformed row must not take the whole file down
    return out


def apply_venue_coordinates(db: Session, dry_run: bool = False) -> LoadResult:
    """Write the exported coordinates onto matching venues.

    Assignment is unconditional where the key matches. The file is the
    verified answer, so "make this database agree with it" is the whole
    contract — and it is what makes the operation idempotent rather than
    dependent on the target's current state. Notably it does *not* consult the
    geocode cache: that check is how `geocode_venues.py` recognises a city
    centroid, and on an environment whose volume carries a thin cache it
    selects nothing and reports success, which is exactly the silent no-op
    this file exists to avoid.
    """
    wanted = venue_coordinates()
    result = LoadResult()
    if not wanted:
        return result

    by_key = {
        (v.source, v.source_venue_id): v
        for v in db.query(Venue).filter(
            Venue.source.isnot(None), Venue.source_venue_id.isnot(None)
        )
    }

    for key, (lat, lon) in wanted.items():
        venue = by_key.get(key)
        if venue is None:
            result.missing += 1
            if len(result.missing_examples) < 10:
                result.missing_examples.append(f"{key[0]}:{key[1]}")
            continue
        # Compared at the CSV's own precision. The export rounds to six
        # decimals — ~0.11m, far finer than any stadium needs — so an exact
        # float comparison would call every row a change on the first load
        # and keep doing so, making "unchanged" useless as a signal that a
        # database already agrees with the file.
        if (
            venue.latitude is not None
            and venue.longitude is not None
            and round(venue.latitude, 6) == round(lat, 6)
            and round(venue.longitude, 6) == round(lon, 6)
        ):
            result.unchanged += 1
            continue
        if not dry_run:
            venue.latitude = lat
            venue.longitude = lon
        result.updated += 1

    if not dry_run:
        db.commit()
    return result
