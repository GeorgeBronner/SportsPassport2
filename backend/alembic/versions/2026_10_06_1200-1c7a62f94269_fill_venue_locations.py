"""fill venue locations the adapters now supply

Revision ID: 1c7a62f94269
Revises: b2c6d1e8f4a7
Create Date: 2026-10-06 12:00:00.000000

A data repair for venue rows that already exist. New imports get these values
from the adapters, but nightly sync never revisits these rows: it doesn't call
CFB `import_venues`, and the 2024/2025 one-off MLB parks will never be synced
again.

- MLB parks Retrosheet's parkcode.txt doesn't list (open_issues.md #13) get
  city, state, country and coordinates from `data/seed/mlb_parks.csv`. A row
  that only ever got its park id as a name gets the real one.
- CFBD's misspelled cities (open_issues.md #11) are corrected, and Orlando City
  Stadium, which the typo kept from being geocoded, gets its coordinates.

Every write fills only a NULL (or, for an MLB name, the bare park id), so the
upgrade never overwrites a better value and is safe to run anywhere. The one
exception is an MLB park's country, which is always set: the model defaults it
to "USA" on insert, so Seoul and Mexico City were never NULL, just wrong, and
nothing but the seed knows better for these parks. The
values are literals rather than reads of the seed CSV, for the reason
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


def upgrade() -> None:
    if not has_table('venues'):
        return
    bind = op.get_bind()

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
                "WHERE source = :source AND source_venue_id = :id AND latitude IS NULL"
            ),
            {'source': source, 'id': source_venue_id, 'lat': lat, 'lon': lon},
        )


def downgrade() -> None:
    # Nothing to undo: the upgrade only filled blanks and fixed typos, and the
    # old values were wrong or missing.
    pass
