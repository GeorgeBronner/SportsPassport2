# SportsPassport2 — Multi-League Game Tracker

App for tracking games attended across **CFB, MLB, NFL, NBA, NHL, CBB** (D-I men's college
basketball) **and MLS**.
Evolution of the original college football tracker (preserved at `../cfb-tracker`). Personal/family
use, Docker-deployed.

Key docs, all under `docs/`: [SP3_plan.md](docs/SP3_plan.md) (build plan + phase status),
[SP3_data_sources.md](docs/SP3_data_sources.md) (data source research),
[open_issues.md](docs/open_issues.md) (known data gaps/defects).

## Tech Stack
- **Backend**: package `sports_passport`. See `backend/CLAUDE.md` for the data model,
  adapter architecture, and compliance rules.
- **Frontend**: built to `backend/static/`, served by FastAPI. See `frontend/CLAUDE.md`
  for the design-token system and layout gotchas.

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
cd backend && uv run uvicorn sports_passport.main:app --reload   # dev server (localhost:8000)
```
