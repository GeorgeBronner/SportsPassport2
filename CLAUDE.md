# SportsPassport2 — Multi-League Game Tracker

App for tracking games attended across **CFB, MLB, NFL, NBA, and NHL** (extensible to MLS etc.).
Evolution of the original college football tracker (preserved at `../cfb-tracker`). Personal/family
use, Docker-deployed.

Key docs: [SP3_plan.md](SP3_plan.md) (build plan + phase status), [SP3_data_sources.md](SP3_data_sources.md)
(data source research), [tasks/todo.md](tasks/todo.md) (current work).

## Tech Stack
- **Backend**: FastAPI, SQLAlchemy, Alembic, SQLite, Pydantic; JWT auth + bcrypt; package `sports_passport`
- **Frontend**: React 18 + TypeScript, Vite, Tailwind CSS, React Router v6, Axios — built to `backend/static/`, served by FastAPI
- **Deploy**: Docker + Docker Compose, single port 8000

## Architecture
- `leagues` is a first-class table; every team/game belongs to one.
- All imported rows are keyed on `(source, source_*_id)` — imports are idempotent upserts.
- One `LeagueAdapter` per league in `backend/sports_passport/services/adapters/`
  (`import_teams` / `import_historical` / `sync_recent`). Registry in `adapters/__init__.py`.
  Adding a league = one adapter module + one seed row.
- Bulk files for historical backfill live in `backend/data/raw/<league>/` (gitignored);
  seed lookups (NBA arenas, team aliases) in `backend/data/seed/` (committed).
- **Compliance rules** (from SP3_data_sources.md — do not violate): MLB Stats API is
  sync-only, never bulk backfill (Retrosheet for that); throttle stats.nba.com; never
  scrape Sports-Reference sites.

## Conventions
- **Git**: feature branches (`feature-name`); merge to `main` when complete and tested. Commit messages concise; **never mention Claude/AI/code-generation tools**.
- **Code organization**: routers focused by domain (auth, leagues, games, teams, attendance, admin); add schemas to the matching schema file; test new endpoints before committing.
- Keep documentation (this file, SP3_plan.md phase checkboxes) updated when features change.

## Common Commands
```bash
cd backend && uv run pytest tests/ -q        # run tests
cd backend && uv run uvicorn sports_passport.main:app --reload   # dev server (localhost:8000)
cd frontend && npm run dev                   # frontend hot-reload dev (localhost:5173)
docker compose up -d --build                 # full build (backend + frontend)
```
