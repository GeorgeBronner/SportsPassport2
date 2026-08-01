# SportsPassport2 — Multi-League Game Tracker

App for tracking games attended across **CFB, MLB, NFL, NBA, NHL, and CBB** (D-I men's college
basketball; extensible to MLS etc.).
Evolution of the original college football tracker (preserved at `../cfb-tracker`). Personal/family
use, Docker-deployed.

Key docs, all under `docs/`: [SP3_plan.md](docs/SP3_plan.md) (build plan + phase status),
[SP3_data_sources.md](docs/SP3_data_sources.md) (data source research),
[SP3_frontend_redesign.md](docs/SP3_frontend_redesign.md) (frontend rebuild plan + phase status),
[SP3_open_issues.md](docs/SP3_open_issues.md) (known data gaps/defects).

## Tech Stack
- **Backend**: FastAPI, SQLAlchemy, Alembic, SQLite, Pydantic; JWT auth + bcrypt; package `sports_passport`
- **Frontend**: React 18 + TypeScript, Vite, Tailwind CSS v4, React Router v6, Axios — built to `backend/static/`, served by FastAPI. Views: Find (omnibox + team workspace), Map (venue atlas), My log (stamps + ledger), Stats (passport page), Admin. Light/dark via CSS-var tokens (see `docs/SP3_frontend_redesign.md`).
- **Deploy**: Docker + Docker Compose, single port 8000

## Architecture
- `leagues` is a first-class table; every team/game belongs to one.
- All imported rows are keyed on `(source, source_*_id)` — imports are idempotent upserts.
- One `LeagueAdapter` per league in `backend/sports_passport/services/adapters/`
  (`import_teams` / `import_historical` / `sync_recent`). Registry in `adapters/__init__.py`.
  Adding a league = one adapter module + one seed row.
- Bulk files for historical backfill live in `backend/data/raw/<league>/` (gitignored).
  Hand-built venue location lookups (city/state/lat-lon) for leagues whose live
  source doesn't carry them — `backend/sports_passport/data/seed/{nfl_stadiums,nhl_arenas,nba_arenas}.csv`,
  loaded via `services/adapters/venue_seed.py` — are committed and wired into
  their adapters; see `docs/SP3_plan.md` Phase 4/7 for scope notes.
  These live **inside the package**, not under `settings.data_dir`: `data_dir` is the
  Docker bind-mount volume (database, logos, `raw/` bulk files), and a mount shadows
  whatever the image put there. Committed code assets belong next to the code that
  reads them — see `tests/test_venue_seed.py` for why.
- **Compliance rules** (from `docs/SP3_data_sources.md` — do not violate): MLB Stats API is
  sync-only, never bulk backfill (Retrosheet for that); throttle stats.nba.com; never
  scrape Sports-Reference sites.

## Conventions
- **Git**: feature branches (`feature-name`); merge to `main` when complete and tested. Commit messages concise; **never mention Claude/AI/code-generation tools**.
- **Code organization**: routers focused by domain (auth, leagues, games, teams, attendance, admin); add schemas to the matching schema file; test new endpoints before committing.
- Keep documentation (this file, `docs/SP3_plan.md` phase checkboxes) updated when features change.

## Common Commands
```bash
cd backend && uv run alembic upgrade head    # apply migrations — required before first run
cd backend && uv run pytest tests/ -q        # run tests
cd backend && uv run uvicorn sports_passport.main:app --reload   # dev server (localhost:8000)
cd frontend && npm run dev                   # frontend hot-reload dev (localhost:5173)
docker compose up -d --build                 # full build (backend + frontend)
```

## Database schema
Alembic owns the schema outright — the app no longer calls `create_all()` at
startup (two authorities for one schema is what broke the migration chain; see
`docs/SP3_open_issues.md` #6). So a new database needs `alembic upgrade head` before
the first `uvicorn`; Docker runs it automatically. Migrations are written
create-if-absent using `sports_passport/db/migration_guards.py`, so `upgrade
head` is safe from any existing database state. `tests/test_migrations.py`
pins both properties, including that a migration-built schema matches the
models — keep it green when adding migrations.
