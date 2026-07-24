"""Schema introspection helpers for Alembic migrations.

This schema predates a working migration chain. The root revision was an empty
stub, so the tables were created by ``Base.metadata.create_all()`` at import
time in ``main.py`` while the later migrations only ``ALTER``-ed on top. That
left two authorities for one schema — ``create_all`` always builds the *current*
models, whereas ``alembic_version`` tracks a history that never created
anything — and they disagree in both directions: "no such table" on an empty
database, "already exists" on one the app has already booted against.

Making every migration create-if-absent is what lets ``upgrade head`` converge
from any of those states without dropping or rewriting a populated table.

Lives in the app package rather than under ``alembic/`` on purpose: that
directory has no ``__init__.py``, so ``from alembic.guards import ...`` would
resolve to the installed Alembic library instead. ``env.py`` already imports
from ``sports_passport``, so this path is guaranteed to work.
"""
import sqlalchemy as sa
from alembic import op


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def has_column(table: str, column: str) -> bool:
    if not has_table(table):
        return False
    return column in {c["name"] for c in _inspector().get_columns(table)}


def has_index(table: str, index: str) -> bool:
    if not has_table(table):
        return False
    return index in {i["name"] for i in _inspector().get_indexes(table)}
