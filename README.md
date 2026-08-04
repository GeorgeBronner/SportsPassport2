# SportsPassport2 — Multi-League Game Tracker

A web application for tracking games you've attended across **CFB, MLB, NFL, NBA, NHL, CBB
(D-I men's college basketball) and MLS**, with statistics and historical game data back to
1970 for the pro leagues (1990 for CFB/CBB, 1996 for MLS).

**Status:** Deployed — staging (`docker31`) and production (Oracle Cloud). See
[docs/SP3_plan.md](docs/SP3_plan.md) for phase progress and
[docs/deployment.md](docs/deployment.md) for the deploy process.

This is the successor to the college-football-only tracker (preserved at `../cfb-tracker`).
Planning docs: [SP3_plan.md](docs/SP3_plan.md) · [SP3_data_sources.md](docs/SP3_data_sources.md) ·
[SP3_frontend_redesign.md](docs/SP3_frontend_redesign.md) · [SP3_open_issues.md](docs/SP3_open_issues.md)

## Features

- **User Authentication** — email/password registration and login with JWT tokens
- **Multi-League Game Database** — historical games per league, each from the best free source:
  | League | Historical | Ongoing sync |
  |--------|-----------|--------------|
  | CFB | CollegeFootballData.com (1990+) | CollegeFootballData.com |
  | MLB | Retrosheet game logs, regular + postseason (1970+) | MLB Stats API |
  | NFL | Kaggle Spreadspoke (1970–1998) + nflverse (1999+) | nflverse games.csv |
  | NBA | Kaggle bulk CSV (1946+) | ESPN scoreboard |
  | NHL | Official NHL API (1970+) | Official NHL API |
  | CBB | CollegeBasketballData.com (1990+) | CollegeBasketballData.com |
  | MLS | Kaggle (1996–2012) + American Soccer Analysis (2013+) | American Soccer Analysis |
- **Attendance Tracking** — mark games attended, add personal notes
- **Statistics Dashboard** — games by league/team/season, unique venues, states visited
- **Venue Atlas** — zoomable US map of every venue, choropleth by state, filterable by league
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
