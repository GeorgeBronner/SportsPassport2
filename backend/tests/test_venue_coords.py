"""The exported venue coordinates, and the loader staging/production run.

Two properties matter here and neither is "the CSV has the right numbers":

1. The file resolves from inside the package, from any working directory.
   `settings.data_dir` is the Docker bind-mount volume, and the mount shadows
   the image's copy of that path — the failure that took the venue seed CSVs
   down in production once already (see test_venue_seed.py).
2. Matching is on `(source, source_venue_id)`, never `venues.id`. The whole
   point of the file is to cross databases, and the autoincrement id does not
   survive the trip.
"""
import csv
import os

import pytest

import sports_passport
from sports_passport.models.venue import Venue
from sports_passport.services import venue_coords
from sports_passport.services.venue_coords import (
    COORDS_PATH,
    apply_venue_coordinates,
    venue_coordinates,
)


@pytest.fixture(autouse=True)
def clear_coord_cache():
    """lru_cache would otherwise mask a path change made mid-test."""
    venue_coordinates.cache_clear()
    yield
    venue_coordinates.cache_clear()


def test_csv_lives_inside_the_package():
    package_root = os.path.dirname(os.path.abspath(sports_passport.__file__))
    assert str(COORDS_PATH).startswith(package_root)
    assert COORDS_PATH.exists()


def test_loads_from_an_unrelated_cwd(tmp_path, monkeypatch):
    """The regression that matters: pytest runs with CWD=backend/, where a
    relative path would happen to resolve. Production's CWD is /app."""
    monkeypatch.chdir(tmp_path)
    venue_coordinates.cache_clear()
    assert len(venue_coordinates()) > 0


def test_keys_are_unique_and_coordinates_are_plausible():
    """A duplicate key would make the applied value depend on row order."""
    with COORDS_PATH.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, "export is empty"

    keys = [(r["source"], r["source_venue_id"]) for r in rows]
    assert len(keys) == len(set(keys))

    for r in rows:
        lat, lon = float(r["latitude"]), float(r["longitude"])
        assert -90 <= lat <= 90, r
        assert -180 <= lon <= 180, r
        # 0,0 is the Atlantic; it is what a failed parse looks like.
        assert (lat, lon) != (0.0, 0.0), r


def _venue(db, source="cfbd", source_venue_id="zzz-test", **kw):
    v = Venue(source=source, source_venue_id=source_venue_id, name="Test Ground", **kw)
    db.add(v)
    db.commit()
    return v


def test_applies_by_natural_key_not_id(db_session, monkeypatch):
    """Two venues, one match. The decoy shares neither source nor venue id, so
    a loader keying on anything positional would move the wrong row."""
    monkeypatch.setattr(
        venue_coords, "venue_coordinates", lambda: {("cfbd", "zzz-test"): (33.2077, -87.5505)}
    )
    decoy = _venue(db_session, source="cbbd", source_venue_id="zzz-decoy",
                   latitude=None, longitude=None)
    target = _venue(db_session, latitude=None, longitude=None)
    assert decoy.id != target.id

    result = apply_venue_coordinates(db_session)

    assert result.updated == 1
    db_session.refresh(target)
    db_session.refresh(decoy)
    assert target.latitude == pytest.approx(33.2077)
    assert target.longitude == pytest.approx(-87.5505)
    assert decoy.latitude is None, "matched on something other than the natural key"


def test_second_run_is_a_no_op(db_session, monkeypatch):
    monkeypatch.setattr(
        venue_coords, "venue_coordinates", lambda: {("cfbd", "zzz-test"): (33.2077, -87.5505)}
    )
    _venue(db_session, latitude=None, longitude=None)

    assert apply_venue_coordinates(db_session).updated == 1
    again = apply_venue_coordinates(db_session)
    assert again.updated == 0
    assert again.unchanged == 1


def test_sub_micro_degree_drift_counts_as_unchanged(db_session, monkeypatch):
    """The export rounds to six decimals. Without matching that precision on
    read, every row reads as changed forever and `unchanged` means nothing."""
    monkeypatch.setattr(
        venue_coords, "venue_coordinates", lambda: {("cfbd", "zzz-test"): (33.2077, -87.5505)}
    )
    _venue(db_session, latitude=33.20770000004, longitude=-87.55050000002)

    result = apply_venue_coordinates(db_session)

    assert result.updated == 0
    assert result.unchanged == 1


def test_venues_absent_from_this_database_are_reported_not_fatal(db_session, monkeypatch):
    monkeypatch.setattr(
        venue_coords,
        "venue_coordinates",
        lambda: {("cfbd", "not-imported-here"): (33.2077, -87.5505)},
    )

    result = apply_venue_coordinates(db_session)

    assert result.missing == 1
    assert result.updated == 0
    assert result.missing_examples == ["cfbd:not-imported-here"]


def test_dry_run_writes_nothing(db_session, monkeypatch):
    monkeypatch.setattr(
        venue_coords, "venue_coordinates", lambda: {("cfbd", "zzz-test"): (33.2077, -87.5505)}
    )
    v = _venue(db_session, latitude=None, longitude=None)

    result = apply_venue_coordinates(db_session, dry_run=True)

    assert result.updated == 1
    db_session.refresh(v)
    assert v.latitude is None


def test_missing_file_yields_no_coordinates_rather_than_raising(monkeypatch, tmp_path):
    """A CSV left out of the image must not crash the container's start-up
    path; the CLI turns the empty result into a non-zero exit instead."""
    monkeypatch.setattr(venue_coords, "COORDS_PATH", tmp_path / "absent.csv")
    venue_coordinates.cache_clear()
    assert venue_coordinates() == {}
