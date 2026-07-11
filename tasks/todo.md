# SportsPassport2 Build — Task Tracker

Working from [SP3_plan.md](../SP3_plan.md). App name stays **SportsPassport2**; the old
college-football-only app was preserved at `../cfb-tracker`.

## Phase 0 — Scaffold ✅
- [x] Copy skeleton from cfb-tracker (backend, frontend, docs, docker-compose; no venv/db/builds)
- [x] Rename package `college_football_tracker` → `sports_passport`; rebrand config/pyproject/compose
- [x] New CLAUDE.md, .gitignore
- [x] Git init, initial commit on `main`
- [x] Verify: full test suite passes; server boots; register/login/leagues round-trip works

## Phase 1 — Core schema + adapter framework ✅
- [x] Models: `leagues` table; generalized `teams`/`venues`/`games` with `(source, source_*_id)` keys,
      `franchise_id`, `neutral_site`, `overtime_flag`, `has_time`
- [x] Alembic reset + initial migration (applies cleanly)
- [x] `LeagueAdapter` ABC + `ImportResult` + registry; shared idempotent upsert helpers (`importer.py`)
- [x] League seeding at startup (CFB/MLB/NFL/NBA/NHL)
- [x] Admin endpoints: `POST /api/admin/import/{league}/teams|historical`, `POST /api/admin/sync/{league}`,
      `GET /api/admin/status`
- [x] Games/teams routers take `league=` filter; new `GET /api/leagues`
- [x] Attendance stats: `games_by_league`, pro teams counted, CFB still FBS-only
- [x] Verify: 110 tests pass incl. new importer/multi-league/admin tests

## Phase 2 — NHL + CFB adapters
- [x] CFB adapter ported from cfb-tracker (`adapters/cfb.py`, source `cfbd`)
- [ ] NHL adapter (`adapters/nhl.py`): teams, historical 1970→now via club-schedule-season, sync via /score/{date}
- [ ] Verify: NHL 2023-24 regular season = 1,312 games; CFB season counts match cfb-tracker DB
- [ ] Live smoke test: import one NHL season, spot-check a known game

## Phase 3 — NFL + MLB adapters
- [ ] Download Kaggle Spreadspoke CSV → `backend/data/raw/nfl/`; NFL adapter + nflverse sync
- [ ] Download Retrosheet game logs → `backend/data/raw/mlb/`; MLB adapter + MLB Stats API sync
- [ ] Verify: NFL 1970 = 182 games; MLB modern season ≈ 2,430 games

## Phase 4 — NBA adapter
- [ ] Build `backend/data/seed/nba_arenas.csv`
- [ ] NBA adapter via nba_api (throttled) or Kaggle CSV fallback
- [ ] Verify: NBA 2023-24 = 1,230 regular season games; >95% venue coverage

## Phase 5 — Frontend multi-league
- [ ] League switcher + all-leagues view; update Team type (`school`→`name` etc.)
- [ ] Game browse/search with league filter; attendance flow unchanged
- [ ] Stats dashboard with league breakdown
- [ ] Verify: manual walkthrough across ≥3 leagues

## Phase 6 — Sync scheduling + deploy
- [ ] Nightly per-league sync (APScheduler); admin UI for status/last-sync
- [ ] Docker deploy; update docs/deployment.md

## Review
_(fill in as phases complete)_
- Phase 0+1 (2026-07-11): Scaffold + multi-league core complete. 110 tests green.
  Smoke-tested: health, register, login, leagues endpoints all working. Old app untouched
  at ../cfb-tracker.
