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

## Phase 2 — NHL + CFB adapters ✅
- [x] CFB adapter ported from cfb-tracker (`adapters/cfb.py`, source `cfbd`)
- [x] NHL adapter (`adapters/nhl.py`): teams (incl. defunct, franchise_id from API),
      historical via standings + club-schedule-season (throttled, deduped), sync via /score/{date}
- [x] Verify: NHL 2023-24 regular season = 1,312 games exact; 1993-94 = 1,092 exact
- [x] Live smoke test: 1994 SCF Game 7 present (VAN 2 @ NYR 3, MSG); postseason 1993-94 = 90
- [x] CFB live verification: 2023 season import via real CFBD API = 3,734 games exact
      (3,595 regular + 139 postseason), matching the old cfb-tracker DB row-for-row
- Note: NHL venues are name-keyed with no city/state from the API — needs a venue
  enrichment seed (fold into Phase 4 seed work) for the states-visited stat to work for NHL.

## Phase 3 — NFL + MLB adapters ✅
- [x] NFL adapter (`adapters/nfl.py`, source `nflverse`): both historical and sync read
      nflverse's `games.csv`/`teams.csv` directly, no local file download needed
- [x] Decision: Kaggle Spreadspoke CSV (would give NFL 1966+) now needs a Kaggle login or
      paid tier — user chose to ship NFL on nflverse alone with a **1999 floor** instead;
      1970-1998 backfill deferred (Phase 7 candidate if a free source appears)
- [x] Verify: 1999 season = 259 games exact (248 regular + 11 postseason); 2020 = 269 exact
      (expanded playoff format); 2023 = 285 exact (17-game season); STL/LA Rams franchise
      linking correct; Super Bowl XXXIV score matches the real result. 5 new tests green
      (120 total).
- [x] MLB adapter (`adapters/mlb.py`, source `retrosheet` bulk + MLB Stats API sync): parses
      Retrosheet's fixed-field gamelog CSV live per season (no local file download), franchise
      links relocated teams via `CurrentNames.csv`, resolves venues with real city/state via
      `parkcode.txt`
- [x] Verify: 1970 season = 1,944 games exact (24 teams × 162/2); 2024 = 2,429 games; opening
      day 1970 score double-checked (Tigers 5, Senators 0, RFK Stadium, attendance 45,015 —
      exact); Expos→Nationals franchise linking correct; MLB Stats API sync resolves onto the
      same rows the bulk import created (130/132 games matched in a spot-check window). 4 new
      tests green (124 total).
- Note: MLB postseason isn't covered (Retrosheet's gamelogs are regular-season only; no
  simple CSV for postseason) — deferred, sync_recent will still catch future postseason games.

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
- Phase 2 NHL (2026-07-11): NHL adapter live-verified against the real API — season game
  counts exact for 2023-24 (1,312) and 1993-94 (1,092), famous-game spot check passed.
  115 tests green. Remaining in phase: CFB live verification (needs CFBD API key run).
- Phase 2 CFB verification (2026-07-11): live season import against the real CFBD API
  (`.env` already had a working key) — 2023 = 3,734 games exact, matching the old
  cfb-tracker DB row-for-row. Phase 2 fully closed.
- Phase 3 NFL (2026-07-11): Kaggle's Spreadspoke CSV (the plan's original NFL historical
  source) now gates its full dataset behind a Kaggle login or $24.99/yr paid tier — no
  longer a plain download. User chose to skip Kaggle entirely and ship NFL on nflverse's
  auth-free `games.csv`/`teams.csv` alone, accepting a 1999 floor instead of 1970. Adapter
  live-verified: 1999/2020/2023 season counts exact, franchise linking (STL/LA Rams) correct,
  Super Bowl XXXIV score double-checked. 120 tests green.
- Phase 3 MLB (2026-07-11): Retrosheet game logs need no auth (unlike NFL's Kaggle blocker) —
  fetched live per season, same pattern as the other three adapters. Discovered the MLB Stats
  API's `teamCode` field matches Retrosheet's historical team codes exactly, which let
  `sync_recent` land on the same rows the Retrosheet bulk import creates instead of needing a
  separate id-mapping table. Live-verified: 1970 season = 1,944 games exact, 2024 = 2,429;
  opening day 1970 score exact match; Expos/Nationals franchise link correct; sync cross-check
  130/132 clean. 124 tests green. Phase 3 fully closed. Next: Phase 4 NBA adapter.
