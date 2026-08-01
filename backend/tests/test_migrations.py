"""
Tests for the Alembic migration chain.

The schema predates a working chain: the root revision was an empty stub, so
tables were created by `Base.metadata.create_all()` while later revisions only
ALTER-ed on top. That produced databases stamped at several different revisions
whose schema was always *ahead* of the stamp, and `alembic upgrade head` failed
from every one of them — "no such table" on an empty database, "already exists"
on a populated one.

These tests pin both halves of the fix: `upgrade head` converges from any of
those states, and a migration-built schema matches what the models declare.
"""
import os
import re
import shutil
import subprocess
import sqlite3
import sys
import tempfile

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEAD = "c4d8e2a1f7b3"

# Revisions real databases have been found stamped at. None = empty database.
# Each non-None case also gets the *current* full schema from create_all, which
# is what makes it a genuine reproduction: the schema is ahead of the stamp.
KNOWN_STATES = [
    pytest.param(None, id="empty-database"),
    pytest.param("c8e2f4a6b1d9", id="stamped-add-venue-coordinates"),
    pytest.param("a7e4c2f1b3d6", id="stamped-sync-state-last-success"),
    pytest.param("e2f5b8c3d4a1", id="stamped-password-reset-tokens"),
    pytest.param("f3a9d4b6c281", id="stamped-unique-user-game-attendance"),
    pytest.param(HEAD, id="already-at-head"),
]


def _run(args, db_path):
    """Run a command against a throwaway database.

    Migrations are exercised through a real subprocess rather than Alembic's
    Python API: that is how Docker runs them, and it is the only way to catch
    an import that resolves differently inside a migration than in the app.
    sys.executable keeps this on the venv interpreter, not whatever `python`
    happens to be first on PATH.
    """
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{db_path}")
    return subprocess.run(
        [sys.executable, *args], cwd=BACKEND_DIR, env=env, capture_output=True, text=True
    )


def _alembic(command, db_path):
    return _run(["-m", "alembic", *command], db_path)


def _create_all(db_path):
    """Build the schema the way main.py does, bypassing migrations entirely."""
    result = _run(
        [
            "-c",
            "from sports_passport.db.database import engine, Base\n"
            "import sports_passport.models  # noqa\n"
            "Base.metadata.create_all(bind=engine)",
        ],
        db_path,
    )
    assert result.returncode == 0, result.stderr


def _current_revision(db_path):
    result = _alembic(["current"], db_path)
    assert result.returncode == 0, result.stderr
    found = re.findall(r"\b([0-9a-f]{12})\b", result.stdout)
    return found[-1] if found else None


def _schema(db_path):
    """Comparable snapshot: columns, defaults, foreign keys, and indexes.

    Column defaults and foreign keys are part of the comparison because they
    are exactly what a narrower snapshot lets drift: a `server_default` present
    in a migration but missing from the model produces two schemas that agree
    on every column name and type, yet make `--autogenerate` emit a phantom
    change on the next revision.
    """
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        snapshot = {}
        tables = con.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name != 'alembic_version'"
        ).fetchall()
        for (table,) in tables:
            columns = {
                # name, type, NOT NULL, DEFAULT — SQLite stores the default as
                # the literal SQL text, so normalise case before comparing.
                (row[1], row[2].upper(), bool(row[3]), (row[4] or "").upper())
                for row in con.execute(f"PRAGMA table_info({table})")
            }
            foreign_keys = {
                (row[2], row[3], row[4])  # referenced table, local col, remote col
                for row in con.execute(f"PRAGMA foreign_key_list({table})")
            }
            index_list = list(con.execute(f"PRAGMA index_list({table})"))
            # Autoindexes are how SQLite implements a table-level UNIQUE
            # constraint. Their generated names carry no meaning, so compare
            # the columns they cover instead.
            unique_cols = {
                tuple(r[2] for r in con.execute(f"PRAGMA index_info({row[1]})"))
                for row in index_list
                if row[2]
            }
            named = {row[1] for row in index_list if not row[1].startswith("sqlite_autoindex")}
            snapshot[table] = (columns, foreign_keys, named, unique_cols)
        return snapshot
    finally:
        con.close()


@pytest.fixture
def tmp_db():
    directory = tempfile.mkdtemp()
    try:
        yield os.path.join(directory, "test.db")
    finally:
        shutil.rmtree(directory, ignore_errors=True)


class TestUpgradeConvergence:
    @pytest.mark.parametrize("stamped_at", KNOWN_STATES)
    def test_upgrade_head_reaches_head(self, stamped_at, tmp_db):
        """`alembic upgrade head` must succeed from every state a real
        database has been found in — the Dockerfile runs it before uvicorn,
        so a failure here means the container never starts."""
        if stamped_at is not None:
            _create_all(tmp_db)
            assert _alembic(["stamp", stamped_at], tmp_db).returncode == 0

        result = _alembic(["upgrade", "head"], tmp_db)
        assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"
        assert _current_revision(tmp_db) == HEAD

    def test_upgrade_head_from_root_stamp_with_no_tables(self, tmp_db):
        """The wreckage the old chain left on every fresh deploy.

        `9182bb4bc1d2` shipped as an empty `pass` stub, so a fresh database
        *committed* it — stamping alembic_version — and only then died at the
        first ALTER in `b4c9e1f7a2d3`. The result is stamped one revision past
        a schema that was never created, and Alembic will not re-run the root.
        Backfilling the root alone therefore does not rescue these; the repair
        has to live in the revision Alembic actually restarts at.
        """
        assert _alembic(["stamp", "9182bb4bc1d2"], tmp_db).returncode == 0
        con = sqlite3.connect(f"file:{tmp_db}?mode=ro", uri=True)
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        con.close()
        assert tables == ["alembic_version"], "precondition: no tables, only the stamp"

        result = _alembic(["upgrade", "head"], tmp_db)
        assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"
        assert _current_revision(tmp_db) == HEAD

        # Reaching head is not enough — the recovered schema has to be the
        # real one, not a partial rebuild that merely stopped erroring.
        directory = tempfile.mkdtemp()
        try:
            reference = os.path.join(directory, "models.db")
            _create_all(reference)
            assert _schema(tmp_db) == _schema(reference)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_upgrade_preserves_existing_rows(self, tmp_db):
        """Migrating a populated database must not touch its data."""
        _create_all(tmp_db)
        assert _alembic(["stamp", "e2f5b8c3d4a1"], tmp_db).returncode == 0

        con = sqlite3.connect(tmp_db)
        con.execute(
            "INSERT INTO users (email, password_hash, full_name, is_admin,"
            " created_at, updated_at) VALUES ('a@b.c','h','A',0,"
            " datetime('now'), datetime('now'))"
        )
        con.execute("INSERT INTO leagues (code, name, sport, active) VALUES ('CFB','x','football',1)")
        con.execute(
            "INSERT INTO teams (league_id, source, source_team_id, name)"
            " VALUES (1,'s','1','T')"
        )
        con.execute(
            "INSERT INTO games (league_id, source, source_game_id, home_team_id,"
            " away_team_id, start_date, season, has_time, neutral_site)"
            " VALUES (1,'s','1',1,1,'2023-01-01',2023,1,0)"
        )
        con.execute(
            "INSERT INTO user_game_attendance (user_id, game_id, notes,"
            " created_at, updated_at) VALUES (1,1,'kept', datetime('now'), datetime('now'))"
        )
        con.commit()
        con.close()

        assert _alembic(["upgrade", "head"], tmp_db).returncode == 0

        con = sqlite3.connect(f"file:{tmp_db}?mode=ro", uri=True)
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("SELECT notes FROM user_game_attendance").fetchall() == [("kept",)]
        assert con.execute("SELECT count(*) FROM games").fetchone()[0] == 1
        con.close()


class TestSchemaParity:
    def test_migrated_schema_matches_models(self, tmp_db):
        """A database built only by migrations must match one built only by
        create_all. Drift between the two is what broke the chain originally;
        it also makes `alembic revision --autogenerate` emit phantom changes."""
        assert _alembic(["upgrade", "head"], tmp_db).returncode == 0
        migrated = _schema(tmp_db)

        directory = tempfile.mkdtemp()
        try:
            from_models_path = os.path.join(directory, "models.db")
            _create_all(from_models_path)
            from_models = _schema(from_models_path)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

        assert set(migrated) == set(from_models), "table sets differ"
        for table in sorted(migrated):
            assert migrated[table] == from_models[table], f"schema differs for {table!r}"
