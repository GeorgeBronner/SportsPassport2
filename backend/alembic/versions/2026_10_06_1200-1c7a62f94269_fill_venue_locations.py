"""fill venue locations the adapters now supply; date-only TBD CFB games

Revision ID: 1c7a62f94269
Revises: b2c6d1e8f4a7
Create Date: 2026-10-06 12:00:00.000000

A data repair for rows that already exist. New imports get these values from
the adapters, but nightly sync never revisits these rows: it doesn't call CFB
`import_venues`, it only re-imports the current CFB season, and the one-off MLB
parks will never be synced again.

- Sync rows created before the Stats API venue-id bridge (open_issues.md #13)
  keyed a one-off park on its raw API name. `_reconcile_legacy_venue` merges
  such a row only when that park is synced again, which for these parks never
  happens, so they are merged here: games move to the park-id row, which takes
  the current name, and the raw row is deleted (attendance references games,
  not venues). A raw row with no park-id twin is just re-keyed.
- MLB parks Retrosheet's parkcode.txt doesn't list (open_issues.md #13) get
  city, state, country and coordinates from `data/seed/mlb_parks.csv`. A row
  that only ever got its park id as a name gets the real one.
- CFBD's misspelled cities (open_issues.md #11) are corrected, and Orlando City
  Stadium, which the typo had geocoded ~250km away, gets its coordinates —
  assigned unconditionally, as `load_venue_coords` does, since a wrong value is
  exactly what this replaces.
- The two pre-2026 CFB games CFBD flags `startTimeTBD` (open_issues.md #7) go
  date-only on their Eastern game day, as `cfb.py` now stores them. The nightly
  sync fixes the current season itself but never re-imports these.

The MLB location fill only writes into a NULL (or, for a name, the bare park
id), so it never overwrites a better value. Country is the exception: the model
defaults it to "USA" on insert, so Seoul and Mexico City were never NULL, just
wrong, and nothing but the seed knows better for these parks. Every statement
matches on a specific key and is a no-op where that key is absent, so the
upgrade is safe on any database, including an empty one. The values are literals rather than reads of the seed CSV, for the reason
`a9f2c7e4b8d1` gives: an applied revision must not change meaning when the
seed is edited later.
"""
from alembic import op
import sqlalchemy as sa

from sports_passport.db.migration_guards import has_table


# revision identifiers, used by Alembic.
revision = '1c7a62f94269'
down_revision = 'b2c6d1e8f4a7'
branch_labels = None
depends_on = None

# Stats API venue name -> Retrosheet park id, for the one-off parks in
# mlb.STATSAPI_VENUE_PARK_IDS. A name absent from a database matches nothing.
LEGACY_PARK_NAMES = [
    ('Sutter Health Park', 'SAC01'),
    ('George M. Steinbrenner Field', 'TAM02'),
    ('Journey Bank Ballpark', 'WIL02'),
    ('Sahlen Field', 'BUF05'),
    ('Rickwood Field', 'BIR01'),
    ('Fort Bragg Field', 'FTB01'),
    ('Gocheok Sky Dome', 'SEO01'),
    ('Estadio Alfredo Harp Helu', 'MEX02'),
    ('London Stadium', 'LON01'),
    ('Field of Dreams', 'DYE01'),
    ('Bristol Motor Speedway', 'BST01'),
]

# park_id, name, city, state, country, latitude, longitude — mirrors mlb_parks.csv
MLB_PARKS = [
    ('BIR01', 'Rickwood Field', 'Birmingham', 'AL', 'USA', 33.5024, -86.8558),
    ('BST01', 'Bristol Motor Speedway', 'Bristol', 'TN', 'USA', 36.5157, -82.2571),
    ('MEX02', 'Estadio Alfredo Harp Helu', 'Mexico City', None, 'Mexico', 19.4037, -99.0852),
    ('SAC01', 'Sutter Health Park', 'West Sacramento', 'CA', 'USA', 38.5804, -121.5134),
    ('SEO01', 'Gocheok Sky Dome', 'Seoul', None, 'South Korea', 37.4982, 126.8671),
    ('TAM02', 'George M. Steinbrenner Field', 'Tampa', 'FL', 'USA', 27.9802, -82.5067),
]

# (wrong city, state, right city) — mirrors venue_seed.CITY_CORRECTIONS
CITY_CORRECTIONS = [
    ('Orlanda', 'FL', 'Orlando'),
    ('Greenbay', 'WI', 'Green Bay'),
]

# (source, source_venue_id, latitude, longitude) — mirrors venue_coordinates.csv
COORDINATES = [
    ('cfbd', '5403', 28.5411, -81.3893),  # Orlando City Stadium
]

# (CFBD game id, Eastern game day) for every pre-2026 startTimeTBD game,
# found by scanning CFBD 1990-2025 on 2026-10-06.
TBD_CFB_GAMES = [
    ('401249415', '2020-11-21'),
    ('401643703', '2024-08-31'),
]


def _merge_legacy_park_rows(bind) -> None:
    for legacy_name, park_id in LEGACY_PARK_NAMES:
        legacy = bind.execute(
            sa.text("SELECT id FROM venues WHERE source = 'retrosheet' AND source_venue_id = :n"),
            {'n': legacy_name},
        ).scalar()
        if legacy is None:
            continue
        canonical = bind.execute(
            sa.text("SELECT id FROM venues WHERE source = 'retrosheet' AND source_venue_id = :p"),
            {'p': park_id},
        ).scalar()
        if canonical is None:
            bind.execute(
                sa.text("UPDATE venues SET source_venue_id = :p WHERE id = :id"),
                {'p': park_id, 'id': legacy},
            )
            continue
        bind.execute(
            sa.text("UPDATE games SET venue_id = :c WHERE venue_id = :l"),
            {'c': canonical, 'l': legacy},
        )
        bind.execute(sa.text("DELETE FROM venues WHERE id = :l"), {'l': legacy})
        bind.execute(
            sa.text("UPDATE venues SET name = :n WHERE id = :c"), {'n': legacy_name, 'c': canonical},
        )


def upgrade() -> None:
    if not has_table('venues'):
        return
    bind = op.get_bind()

    _merge_legacy_park_rows(bind)

    for park_id, name, city, state, country, lat, lon in MLB_PARKS:
        bind.execute(
            sa.text(
                "UPDATE venues SET "
                "name = CASE WHEN name = :park_id THEN :name ELSE name END, "
                "city = COALESCE(city, :city), state = COALESCE(state, :state), "
                "country = :country, "
                "latitude = COALESCE(latitude, :lat), longitude = COALESCE(longitude, :lon) "
                "WHERE source = 'retrosheet' AND source_venue_id = :park_id"
            ),
            {'park_id': park_id, 'name': name, 'city': city, 'state': state,
             'country': country, 'lat': lat, 'lon': lon},
        )

    for wrong, state, right in CITY_CORRECTIONS:
        bind.execute(
            sa.text("UPDATE venues SET city = :right WHERE city = :wrong AND state = :state"),
            {'wrong': wrong, 'state': state, 'right': right},
        )

    for source, source_venue_id, lat, lon in COORDINATES:
        bind.execute(
            sa.text(
                "UPDATE venues SET latitude = :lat, longitude = :lon "
                "WHERE source = :source AND source_venue_id = :id"
            ),
            {'source': source, 'id': source_venue_id, 'lat': lat, 'lon': lon},
        )


    if has_table('games'):
        for game_id, day in TBD_CFB_GAMES:
            bind.execute(
                sa.text(
                    "UPDATE games SET has_time = 0, start_date = :start "
                    "WHERE source = 'cfbd' AND source_game_id = :id AND has_time = 1"
                ),
                {'id': game_id, 'start': f'{day} 12:00:00.000000'},
            )


def downgrade() -> None:
    # Nothing to undo: the upgrade only filled blanks, fixed typos, merged
    # duplicate rows and dropped placeholder times; the old values were wrong
    # or missing, and the placeholders are not worth restoring.
    pass
