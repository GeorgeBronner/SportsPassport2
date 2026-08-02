# SportsPassport2 — Multi-League Game Tracker

App for tracking games attended across **CFB, MLB, NFL, NBA, NHL, CBB** (D-I men's college
basketball) **and MLS**.
Evolution of the original college football tracker (preserved at `../cfb-tracker`). Personal/family
use, Docker-deployed.

Key docs, all under `docs/`: [SP3_plan.md](docs/SP3_plan.md) (build plan + phase status),
[SP3_data_sources.md](docs/SP3_data_sources.md) (data source research),
[SP3_frontend_redesign.md](docs/SP3_frontend_redesign.md) (frontend rebuild plan + phase status),
[SP3_open_issues.md](docs/SP3_open_issues.md) (known data gaps/defects).

## Tech Stack
- **Backend**: FastAPI, SQLAlchemy, Alembic, SQLite, Pydantic; JWT auth + bcrypt; package `sports_passport`
- **Frontend**: React 18 + TypeScript, Vite, Tailwind CSS v4, React Router v6, Axios — built to `backend/static/`, served by FastAPI. Views: Find (omnibox + team workspace), Map (venue atlas), My log (stamps + ledger), Passport (stats/identity page), Admin. Light/dark via CSS-var tokens (see `docs/SP3_frontend_redesign.md`; the 2026-08-02 refactor pass is `docs/8-2-26-frontend-refactor.md`).
  **Every page is on the token system** — there is no legacy `primary-*`/`accent-*`/`sage-*`
  palette any more, so a new page should reach for `bg-panel` / `text-ink` / `border-line`,
  never a fixed Tailwind colour that can't follow the theme.
  Two traps worth knowing before touching layout:
  `overflow-x: auto` computes the **other** axis to `auto` as well — that silently turns a
  panel into a scroll container, which breaks any `position: sticky` inside it and adds
  stray vertical scrollbars; scope it (`max-lg:overflow-x-auto`) or pair it with an explicit
  `overflow-y-hidden`. And an SVG with a fixed `viewBox` plus `w-full` scales its **text**
  with the box, so a chart sized for a 300px rail renders 37px labels in a full-width panel —
  size the viewBox from the measured container instead (`components/find/SeasonChart.tsx`).
- **Deploy**: Docker + Docker Compose, single port 8000

## Architecture
- `leagues` is a first-class table; every team/game belongs to one.
- All imported rows are keyed on `(source, source_*_id)` — imports are idempotent upserts.
- One `LeagueAdapter` per league in `backend/sports_passport/services/adapters/`
  (`import_teams` / `import_historical` / `sync_recent`). Registry in `adapters/__init__.py`.
  Adding a league = one adapter module + one seed row.
- Bulk files for historical backfill live in `backend/data/raw/<league>/` (gitignored).
  Hand-built venue location lookups (city/state/lat-lon) for leagues whose live
  source doesn't carry them — `backend/sports_passport/data/seed/{nfl_stadiums,nhl_arenas,nba_arenas,mls_stadiums}.csv`,
  loaded via `services/adapters/venue_seed.py` — are committed and wired into
  their adapters; see `docs/SP3_plan.md` Phase 4/7 for scope notes. `nfl_stadiums.csv`
  also carries 29 `hist-`-prefixed rows for pre-1999 grounds nflverse never saw; the
  prefix keeps them from ever colliding with a real nflverse `stadium_id`.
  `games.start_date` is **always UTC**; the NBA (Kaggle) and NFL (nflverse) bulk
  files publish US Eastern instead, and are converted on import via
  `services/adapters/local_time.py` — see `docs/SP3_open_issues.md` #7.
  Games with a known date but no real start time (`has_time=False`) are parked at
  **noon** UTC via `local_time.date_only()`, never midnight — midnight renders as
  the previous day anywhere west of Greenwich if a consumer forgets to pin the row
  to UTC. Use the helper rather than restating the hour; see `SP3_open_issues.md` #8.
  **MLS and NFL are each on two sources, split at a hard season boundary**, so the
  same game can never arrive twice. MLS: the ASA API owns 2013+ and sync, a Kaggle
  bulk file owns 1996–2012 (`FIRST_ASA_SEASON`). ASA's `/stadia` is the one
  crossover — the Kaggle era reads it so a ground both eras used lands on one venue
  row — and is allowed to fail so a pre-2013 import stays a local CSV read.
  NFL: nflverse owns 1999+ and all sync, the Kaggle "Spreadspoke" bulk file owns
  1970–1998 (`FIRST_NFLVERSE_SEASON`). The split is on the **season**, not the date,
  so the January-1999 playoffs of the 1998 season stay with their own season. Both
  NFL eras share `source = "nflverse"` deliberately: 31 of the 64 pre-1999 stadiums
  are buildings nflverse also knows, and `upsert_venue` keys on
  `(source, source_venue_id)`, so a separate source string would duplicate every one
  of them. Team identity is keyed on `source_team_id`, never `abbreviation` — the
  pre-1999 era reuses codes the modern league reassigned (the Oilers were "HOU",
  now the Texans).
  `venues.state` is a **2-letter code** in every league; the attendance stats group
  on it directly, so long-form names split a state into two buckets.
  These live **inside the package**, not under `settings.data_dir`: `data_dir` is the
  Docker bind-mount volume (database, logos, `raw/` bulk files), and a mount shadows
  whatever the image put there. Committed code assets belong next to the code that
  reads them — see `tests/test_venue_seed.py` for why.
- **Compliance rules** (from `docs/SP3_data_sources.md` — do not violate): MLB Stats API is
  sync-only, never bulk backfill (Retrosheet for that); ESPN's hidden API (NBA sync,
  team logos) is unofficial — throttled, descriptive User-Agent, never bulk; never
  scrape Sports-Reference sites (this includes **FBref**, for MLS). nba.com is
  Akamai-blocked from our hosts and is no longer used at all. The ASA API (MLS)
  publishes no formal terms but ships first-party MIT clients, so it gets the same
  posture as ESPN — descriptive User-Agent and polite pacing.

## Conventions
- **Git**: feature branches (`feature-name`); merge to `main` when complete and tested. Commit messages concise; **never mention Claude/AI/code-generation tools**.
- **Before opening a PR**, all four must be clean — nothing here runs in CI, so the
  only thing standing between a defect and `main` is running them locally:
  ```bash
  cd backend && uv run ruff check . && uv run pyright && uv run pytest tests/ -q
  cd frontend && npm run lint
  ```
  All four are at **zero** errors and warnings, and must stay there — any output at
  all is something the branch introduced. Prefer fixing the cause over adding a
  `noqa` / `pyright: ignore` / `eslint-disable`; when a suppression really is right
  (a third-party stub is wrong, an import exists only for its side effect), scope it
  to the one rule and say why in a comment — see `alembic/env.py` and
  `core/config.py` for the shape.
- **Code organization**: routers focused by domain (auth, leagues, games, teams, attendance, admin); add schemas to the matching schema file; test new endpoints before committing.
- Keep documentation (this file, `docs/SP3_plan.md` phase checkboxes) updated when features change.

## Common Commands
```bash
cd backend && uv run alembic upgrade head    # apply migrations — required before first run
cd backend && uv run pytest tests/ -q        # run tests
cd backend && uv run ruff check .            # lint (--fix to auto-fix)
cd backend && uv run pyright                 # type check
cd backend && uv run uvicorn sports_passport.main:app --reload   # dev server (localhost:8000)
cd frontend && npm run dev                   # frontend hot-reload dev (localhost:5173)
cd frontend && npm run lint                  # frontend lint (ESLint)
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

Models use SQLAlchemy 2.0 typed declarative: `name: Mapped[str] = mapped_column(...)`,
never bare `Column(...)`. **The annotation is what sets nullability** — `Mapped[str]`
is `NOT NULL`, `Mapped[str | None]` is nullable — so a wrong annotation silently
changes the schema rather than failing loudly. Don't restate `nullable=` alongside
it. `tests/test_migrations.py` is what catches a mistake here.
