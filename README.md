# SportsPassport2 — Multi-League Game Tracker

A web application for tracking games you've attended across **College Football, MLB, NFL, NBA,
and NHL**, with statistics and historical game data back to 1970 (1990 for CFB). Built to be
extensible to future leagues (MLS, etc.).

**Status:** 🚧 In development — see [docs/SP3_plan.md](docs/SP3_plan.md) for phase progress.

This is the successor to the college-football-only tracker (preserved at `../cfb-tracker`).
Planning docs: [SP3_plan.md](docs/SP3_plan.md) · [SP3_data_sources.md](docs/SP3_data_sources.md) ·
[SP3_frontend_redesign.md](docs/SP3_frontend_redesign.md) · [SP3_open_issues.md](docs/SP3_open_issues.md)

## Features

- **User Authentication** — email/password registration and login with JWT tokens
- **Multi-League Game Database** — historical games per league, each from the best free source:
  | League | Historical | Ongoing sync |
  |--------|-----------|--------------|
  | CFB | CollegeFootballData.com (1990+) | CollegeFootballData.com |
  | MLB | Retrosheet game logs (1970+) | MLB Stats API |
  | NFL | Kaggle/Spreadspoke CSV (1970+) | nflverse games.csv |
  | NBA | stats.nba.com via nba_api (1970+) | nba_api |
  | NHL | Official NHL API (1970+) | Official NHL API |
- **Attendance Tracking** — mark games attended, add personal notes
- **Statistics Dashboard** — games by league/team/season, unique venues, states visited
- **Admin** — per-league import/sync endpoints, data status, user management

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Alembic, SQLite, JWT auth — package `sports_passport`
- **Frontend**: React 18 + TypeScript, Vite, Tailwind CSS
- **Deploy**: Docker & Docker Compose, single container, port 8000

## Development

```bash
# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn sports_passport.main:app --reload   # http://localhost:8000

# Tests
uv run pytest tests/ -q

# Frontend dev server
cd frontend && npm install && npm run dev           # http://localhost:5173

# Full Docker build
docker compose up -d --build
```

Configuration lives in `backend/.env` (see `backend/.env.example`). A
CollegeFootballData.com API key is optional but recommended for CFB imports; all other
league sources are keyless.
