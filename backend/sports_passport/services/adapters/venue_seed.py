"""Hand-built venue location lookups for leagues whose live source doesn't
carry city/state (NFL, NHL) or is historically sparse for venue info (NBA,
pre-current-season) — see sports_passport/data/seed/*.csv. Coordinates are
supplied directly (arena/stadium-level precision) rather than routing through
scripts/geocode_venues.py, since these are small, finite, hand-verified lists.

These CSVs live *inside the package*, not under `settings.data_dir`. They are
small, committed, and versioned in lockstep with the adapters that read them —
code assets, not runtime state. `data_dir` is the Docker bind-mount volume
(database, scraped logos, bulk `raw/` downloads); anything placed there by the
image is shadowed by the mount at runtime, which is exactly how an earlier
`data_dir`-relative version of this module shipped a `FileNotFoundError` into
the nightly NFL/NHL/NBA sync. Resolving from `__file__` keeps one source of
truth that works identically in a dev checkout and in the container.

NHL and NBA are keyed by (team, season-range) rather than by venue name/id,
since neither source gives a stable physical-venue identifier and NHL arena
names in particular change on every naming-rights deal — keying by team+era
means a rename just updates the `name` on the existing venue row instead of
silently orphaning a new, uncoordinated one. NFL is keyed by nflverse's own
stadium_id, which is already stable across renames.

MLS is keyed by canonical venue name, because its two sources identify a venue
only by name: the ASA API's `stadia` endpoint carries coordinates for most
modern grounds but not all, and the Kaggle bulk file (1996-2012) has no venue
IDs at all. mls.py canonicalizes the raw name first — collapsing naming-rights
eras and spelling variants onto one building — and looks the result up here.
Coordinates were geocoded via Nominatim rather than hand-entered.

Several MLS entries are demolished grounds whose coordinates resolve to the
successor stadium built on or beside the same site (Foxboro Stadium/Gillette,
Mile High Stadium/Empower Field, Houlihan's Stadium/Raymond James, Giants
Stadium/Meadowlands). They stay separate venue rows — they are genuinely
different buildings, and a venue someone attended should not be silently
merged into its replacement — so a handful of pairs share coordinates to
within a few hundred metres. That is well inside the precision this map needs.
"""
import csv
from functools import lru_cache
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "seed"


def _seed_path(filename: str) -> Path:
    return SEED_DIR / filename


@lru_cache(maxsize=1)
def nfl_stadiums() -> dict[str, dict]:
    """nflverse stadium_id -> seed row."""
    with open(_seed_path("nfl_stadiums.csv"), newline="", encoding="utf-8") as f:
        return {row["stadium_id"]: row for row in csv.DictReader(f)}


def _load_by_key(filename: str, key_column: str) -> dict[str, list[dict]]:
    by_key: dict[str, list[dict]] = {}
    with open(_seed_path(filename), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_key.setdefault(row[key_column], []).append(row)
    return by_key


def _lookup_by_season(rows_by_key: dict[str, list[dict]], key: str, season: int) -> dict | None:
    """The row (from rows_by_key[key]) whose [start_season, end_season] covers this season."""
    for row in rows_by_key.get(key, []):
        start = int(row["start_season"])
        end = int(row["end_season"]) if row["end_season"] else None
        if season >= start and (end is None or season <= end):
            return row
    return None


@lru_cache(maxsize=1)
def _nba_arenas_by_team() -> dict[str, list[dict]]:
    return _load_by_key("nba_arenas.csv", "team_id")


def lookup_nba_arena(team_id: str, season: int) -> dict | None:
    return _lookup_by_season(_nba_arenas_by_team(), str(team_id), season)


@lru_cache(maxsize=1)
def _nba_arenas_by_name() -> dict[str, dict]:
    """Arena name -> seed row, across every team and era.

    Lets a caller that already knows the building by name (Games.csv carries
    arena data for its current season) land on the same venue row the
    team+era lookup produces, instead of minting a second row for the same
    arena under a different key.
    """
    by_name: dict[str, dict] = {}
    for rows in _nba_arenas_by_team().values():
        for row in rows:
            by_name.setdefault(row["arena"], row)
    return by_name


def lookup_nba_arena_by_name(arena: str) -> dict | None:
    return _nba_arenas_by_name().get(arena)


@lru_cache(maxsize=1)
def _mls_stadiums() -> dict[str, dict]:
    """Canonical venue name -> seed row."""
    with open(_seed_path("mls_stadiums.csv"), newline="", encoding="utf-8") as f:
        return {row["name"]: row for row in csv.DictReader(f)}


def lookup_mls_stadium(name: str) -> dict | None:
    """Coordinates for an MLS ground, keyed by its canonical name.

    Covers both what ASA omits (8 of its 56 stadia carry no lat/lon) and the
    pre-2013 grounds the Kaggle bulk file references but ASA never lists.
    """
    return _mls_stadiums().get(name)


@lru_cache(maxsize=1)
def _nhl_arenas_by_tricode() -> dict[str, list[dict]]:
    return _load_by_key("nhl_arenas.csv", "tricode")


def lookup_nhl_arena(tricode: str, season: int) -> dict | None:
    """The physical-arena-era row (team + season range) covering this season —
    keyed by team rather than by the API's display name, so a naming-rights
    rename never breaks the lookup (see nhl.py's _upsert_api_game)."""
    return _lookup_by_season(_nhl_arenas_by_tricode(), tricode, season)


def venue_fields(row: dict) -> dict:
    """city/state/country/latitude/longitude kwargs for upsert_venue, blanks as None."""
    return {
        "city": row.get("city") or None,
        "state": row.get("state") or None,
        "country": row.get("country") or None,
        "latitude": float(row["latitude"]) if row.get("latitude") else None,
        "longitude": float(row["longitude"]) if row.get("longitude") else None,
    }
