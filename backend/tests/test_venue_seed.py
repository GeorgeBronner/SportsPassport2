"""Seed CSVs must resolve from the package, not from the working directory.

Regression cover for the FileNotFoundError that reached production: the seeds
were read from `settings.data_dir/seed/`, which is the Docker bind-mount volume.
The image's copy of that path is shadowed by the mount at runtime, so every
deployed NFL/NHL/NBA import and nightly sync raised
`No such file or directory: 'data/seed/nfl_stadiums.csv'`.

The adapter tests never caught it because pytest runs with CWD=backend/, where
the relative path happened to resolve. So the property worth pinning is not
"the loaders work" but "the loaders work from an unrelated CWD".
"""
import os

import pytest

import sports_passport
from sports_passport.services.adapters import venue_seed

SEED_LOADERS = (
    venue_seed.nfl_stadiums,
    venue_seed._nba_arenas_by_team,
    venue_seed._nhl_arenas_by_tricode,
)


def _clear_caches():
    for loader in SEED_LOADERS:
        loader.cache_clear()


@pytest.fixture(autouse=True)
def clear_seed_caches():
    """lru_cache would otherwise mask a path change made mid-test."""
    _clear_caches()
    yield
    _clear_caches()


def test_seed_dir_lives_inside_the_package():
    """Not under data_dir — that path is the bind-mount volume in Docker."""
    package_root = os.path.dirname(sports_passport.__file__)
    assert str(venue_seed.SEED_DIR).startswith(package_root)
    assert venue_seed.SEED_DIR.is_dir()


def test_seed_files_load_from_an_unrelated_cwd(tmp_path, monkeypatch):
    """The actual production failure: correct CWD is not a precondition."""
    monkeypatch.chdir(tmp_path)
    _clear_caches()

    assert len(venue_seed.nfl_stadiums()) > 0
    assert len(venue_seed._nba_arenas_by_team()) > 0
    assert len(venue_seed._nhl_arenas_by_tricode()) > 0


def test_lookups_return_usable_rows_from_an_unrelated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _clear_caches()

    nhl = venue_seed.lookup_nhl_arena("TOR", 2024)
    assert nhl and nhl["city"] == "Toronto"

    # 1610612747 = Lakers; Crypto.com Arena era starts 1999.
    nba = venue_seed.lookup_nba_arena("1610612747", 2015)
    assert nba and nba["city"] == "Los Angeles"

    fields = venue_seed.venue_fields(nhl)
    assert isinstance(fields["latitude"], float)
    assert isinstance(fields["longitude"], float)


def test_every_seed_row_carries_usable_coordinates():
    """These seeds exist to put venues on the map; a row without coords is a
    silently invisible dot, so the CSVs are the wrong place to be lenient.

    Parsed rather than merely checked for presence: `venue_fields` runs both
    values through `float()`, so a malformed one survives a truthiness test
    and raises mid-sync instead.
    """
    rows = list(venue_seed.nfl_stadiums().values())
    for by_key in (venue_seed._nba_arenas_by_team(), venue_seed._nhl_arenas_by_tricode()):
        for group in by_key.values():
            rows.extend(group)

    bad = []
    for row in rows:
        try:
            fields = venue_seed.venue_fields(row)
        except (TypeError, ValueError):
            bad.append(row)
            continue
        if fields["latitude"] is None or fields["longitude"] is None:
            bad.append(row)
        elif not (-90 <= fields["latitude"] <= 90 and -180 <= fields["longitude"] <= 180):
            bad.append(row)

    assert not bad, f"seed rows with missing or unusable coordinates: {bad}"
