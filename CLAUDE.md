# College Football Game Tracker

App for tracking college football games attended, with statistics and historical game data (1990-present from [CollegeFootballData.com](https://api.collegefootballdata.com)). Personal/family use, Docker-deployed.

## Tech Stack
- **Backend**: FastAPI, SQLAlchemy, Alembic, SQLite, Pydantic; JWT auth + bcrypt
- **Frontend**: React 18 + TypeScript, Vite, Tailwind CSS, React Router v6, Axios — built to `backend/static/`, served by FastAPI
- **Deploy**: Docker + Docker Compose, single port 8000, Alembic migrations auto-run on startup

## Conventions
- **Git**: feature branches (`feature-name`); merge to `main` when complete and tested. Commit messages concise; **never mention Claude/AI/code-generation tools**.
- **Code organization**: routers focused by domain (auth, games, teams, attendance, admin); add schemas to the matching schema file; test new endpoints before committing.
- **After merging to main**: rebuild and verify — `docker compose up -d --build` then `docker logs cfb-tracker-backend --tail 10`.
- Keep documentation (this file and `docs/`) updated when features or requirements change.

## Common Commands
```bash
docker compose up -d --build              # full build (backend + frontend)
docker compose exec backend pytest tests/ -v   # run tests
cd frontend && npm run dev                # frontend hot-reload dev (localhost:5173)
```

## Documentation
- [docs/requirements.md](docs/requirements.md) — full product requirements and feature status
- [docs/deployment.md](docs/deployment.md) — Oracle production deployment, env vars, network, troubleshooting
- [docs/testing.md](docs/testing.md) — test structure and how to run tests
- [docs/frontend.md](docs/frontend.md) — frontend pages, features, and dev workflow
