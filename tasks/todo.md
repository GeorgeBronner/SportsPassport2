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

## Phase 4 — NBA adapter ✅ (uncommitted)
- [x] Confirmed `stats.nba.com` is unreachable from this dev sandbox (Akamai anti-bot
      TLS challenge, not rate limiting — `curl` hangs on SSL renegotiation)
- [x] User downloaded the Kaggle CSV manually: `eoinamoore/historical-nba-data-and-
      player-box-scores` dataset, `Games.csv` file only. Now at
      `backend/data/raw/nba/Games.csv` (73,279 rows, 1946-2026, gitignored)
- [x] NBA adapter written (`adapters/nba.py`, source `nba-kaggle`) and registered in
      `adapters/__init__.py`. `import_teams`/`import_historical` parse the local CSV;
      franchise linking via NBA's stable numeric team id; season derived from the
      `gameId` encoding (not date, because of the 2019-20 COVID-delayed playoffs)
- [x] **NBA Cup miscount fixed (2026-07-12):** the championship final (a standalone
      game, `gameId` type digit `"6"`) doesn't count toward any team's record, unlike
      the 66 in-season-tournament group-stage games which do. Split it into its own
      `season_type = "cup_final"`. 2023-24 now imports exactly 1,230 regular season
      games.
- [x] `test_nba_adapter.py` written (6 tests) + `nba_league` fixture added to
      conftest.py. 130 tests green (up from 124).
- [x] **Two real bugs found + fixed in `sync_recent` while writing its test**
      (found via API-shape review, not live testing — still unreachable here):
      `stats.nba.com`'s `GAME_ID` is 10 chars (2-char league prefix + the same
      8-char form the Kaggle CSV uses), but the code was feeding the raw 10-char id
      into season parsing (misreads the season by 2 digits) and storing it as
      `source_game_id` (would never match the bulk import's 8-char ids — every
      synced game would've landed as a duplicate instead of updating the historical
      row). Fixed by stripping the league prefix before both uses.
- [x] Full backfill run: `import_historical(1946, 2025)` against the real local file
      = **73,272 games, zero errors.** Gap vs. 73,279 CSV rows is exactly the
      intentionally-excluded All-Star Games (7). 63 teams, 47 venues.
- [ ] `sync_recent` still needs a real end-to-end run against `stats.nba.com` from a
      network that can reach it (post-deploy) — parsing is now correct against the
      documented response shape, but that's an unofficial endpoint that can drift
- [x] **Decision (2026-07-12):** `data/seed/nba_arenas.csv` deferred to Phase 7 —
      user chose to ship NBA with sparse venue coverage (current-era games only,
      1,393 of 73,272) for the first draft rather than block Phase 4 on manual
      research. Phase 4 is otherwise closed.
- Full details, exact next steps, and reasoning are in **SP3_plan.md's Phase 4 section**
  — read that first before continuing this phase.
- **Nothing from this phase is committed.** `git status` will show `nba.py`,
  `adapters/__init__.py`, `core/config.py` (added `nba_stats_api_url`),
  `test_nba_adapter.py`, `conftest.py`, and this file / SP3_plan.md as modified/new,
  plus the untracked (gitignored) `Games.csv`.

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
- Phase 4 NBA (2026-07-11, PAUSED mid-phase at user's request): hit the same "official
  source unreachable" problem as NFL's Kaggle blocker, but worse — `stats.nba.com` isn't
  just gated, it's flat-out unreachable from this dev sandbox (Akamai TLS challenge).
  User downloaded the Kaggle Games.csv fallback manually. Adapter written and
  smoke-verified against the real local file for one season (1,383 games, 0 errors,
  franchise linking confirmed) but the work is NOT finished: sync_recent is
  unverified (can't reach stats.nba.com to test it), no unit tests exist, the arena
  seed file for historical venues was never started, and only one season was
  smoke-tested (not the full 1946-2025 backfill). CFB/NHL/NFL/MLB (Phases 2-3) are
  fully done and committed (commit 3fdcb24); this NBA work is uncommitted on disk.
  Pick up from SP3_plan.md's Phase 4 section, which has the full next-steps list.
- Phase 4 NBA continued (2026-07-12): fixed the NBA Cup championship-final miscount
  (it's a standalone game that doesn't count toward either team's record, unlike the
  in-season-tournament group-stage games — gave it its own `season_type`). Wrote
  `test_nba_adapter.py` (6 tests) + `nba_league` fixture; 130 tests green. Writing the
  sync test surfaced two real bugs in `sync_recent`'s untested code path — a season-
  parsing off-by-2 and a source_game_id mismatch that would've caused every synced
  game to duplicate instead of updating the historical row — both fixed by correctly
  stripping stats.nba.com's league-id prefix. Ran the full 1946-2025 backfill locally:
  73,272 games, zero unmatched-team errors. Remaining before Phase 4 closes: a live
  end-to-end test of `sync_recent` from a network that can reach stats.nba.com (not
  this sandbox), and the `data/seed/nba_arenas.csv` venue research pass (~120 rows,
  manual Wikipedia lookup — not a coding task, needs a scoping decision on when/how
  to do it or whether to defer to Phase 5+).
