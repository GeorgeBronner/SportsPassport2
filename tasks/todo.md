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

## Phase 4 — NBA adapter ✅
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
- **Committed** in `4065c9a` (`nba.py`, `adapters/__init__.py`, `core/config.py`,
  `test_nba_adapter.py`, `conftest.py`, `SP3_plan.md`/this file); `Games.csv` stays
  untracked/gitignored as intended.

## Phase 5 — Frontend multi-league ✅
- [x] Rewrote `types/api.ts` + all API clients to match the real backend schemas (was still
      the pre-Phase-1 `school`/`mascot`/`api_team_id` shape); added `api/leagues.ts`,
      rewrote `api/admin.ts` for the real per-league endpoints
- [x] League filter on Games/browse page (chip dropdown, not a global header switcher —
      see SP3_plan.md Phase 5 for why); team/season lists re-scope on league change
- [x] `GameCard`/`MyGames`/`Admin` ported off old field names; added league + OT/SO badges,
      team-name links to new team pages
- [x] New `/teams/:id` page with franchise-history timeline; needed `GET /api/teams/{id}`
      + `franchise_id` filter added to the backend (4 new tests, 134 total)
- [x] Dashboard + Statistics: "Games by League" section
- [x] Admin page rebuilt: per-league import teams/historical/sync actions + status table
- [x] Fixed a real date-shift bug (hardcoded America/Chicago rolled historical MLB dates back
      a day) and a real NHL data gap (missing first_season/last_season broke franchise-history
      ordering) — both found during this phase, details in SP3_plan.md
- [x] Verify: full browser walkthrough (Chrome tools) against live cross-league data —
      login, league-filtered browse, attendance across 3 leagues, dashboard/stats numbers,
      team franchise page, admin import action. Zero console errors. 134 backend tests green,
      `tsc -b` + `vite build` clean.
- Deferred: per-league "passport completion" stat (no endpoint, ambiguous semantics — see
  SP3_plan.md)

## Phase 6 — Sync scheduling + deploy
- [ ] Nightly per-league sync (APScheduler); admin UI for status/last-sync
- [ ] Docker deploy; update docs/deployment.md

## Phase 8 — CBB adapter (added beyond original scope) ✅
- [x] `CbbAdapter` (`adapters/cbb.py`, source `cbbd`) built on CollegeBasketballData.com,
      reusing the existing `CFB_API_KEY` (live-confirmed to work unmodified as a CBBD token)
- [x] Corrected two research findings via live testing: real floor is ~1950+, not 2003
      (1990 chosen anyway, matching CFB's floor); `/games` caps at exactly 3000 rows
      regardless of season/seasonType filters — real pagination is via
      `startDateRange`/`endDateRange`, chunked monthly
- [x] Classification (`d1`/`non-d1`) read from each game's own conference field, no extra
      per-season roster calls needed; non-D-I buy-game opponents get full team rows
      (school/mascot/abbreviation) from CBBD's all-time `/teams` registry, no manual seed
      lookup needed (verified against a real IU Indianapolis vs. Spalding/NAIA game)
- [x] `test_cbb_adapter.py` (6 tests) + `cbb_league` fixture; 140 tests green
- [x] Live verification: 2023 season alone = 6,243 games, 0 errors, 365 D-I teams (exact
      match to the research's team-count estimate); full 1990-2024 backfill (35 seasons) =
      179,107 games, zero unmatched-team errors, 1,386 teams, 749 venues, ~179s
- Full details in **SP3_plan.md's Phase 8 section**
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
- Phase 5 Frontend (2026-07-12): the frontend was still entirely the pre-Phase-1
  cfb-tracker UI — types and API clients used field names (`school`, `mascot`,
  `api_team_id`) that stopped matching the backend back in Phase 1. Rewrote both,
  added the league dimension throughout, and added team detail pages with franchise
  history (needed two small new backend endpoints). Found and fixed two real
  pre-existing bugs along the way: a hardcoded-timezone date formatter that rolled
  historical MLB game dates back a day, and a missing NHL data field that made
  franchise-history ordering wrong (worked around at the UI layer; the real fix is
  separate follow-up work, logged in SP3_plan.md under Phase 2). Full browser
  walkthrough against live cross-league data confirmed the whole flow end-to-end —
  login, league-filtered browsing, attendance across 3 leagues, dashboard/stats
  numbers, team pages, and a real admin import action — with zero console errors.
  134 backend tests green, clean typecheck and production build. Deferred:
  per-league "passport completion" stat (no backend support yet, ambiguous
  semantics). Next: Phase 6 (sync scheduling + deploy).
- Phase 8 CBB adapter (2026-07-12): built on CollegeBasketballData.com, reusing the
  existing CFBD key (live-confirmed to work unmodified). Live testing while building
  the adapter corrected two things the earlier research got wrong without live API
  access: the real data floor is ~1950+, not 2003 (app ships with 1990 anyway, matching
  CFB, as a scope choice not a data limit); and `/games` caps at exactly 3,000 rows
  regardless of season/seasonType filters, requiring date-range chunking instead.
  Classification (d1/non-d1) reads off each game's own conference field rather than
  needing extra per-season roster calls, and non-D-I buy-game opponents get full team
  identity from CBBD's all-time /teams registry with no manual seed lookup needed —
  both simpler than the original research assumed. 140 tests green. Full 1990-2024
  backfill: 179,107 games, zero unmatched-team errors, 1,386 teams, 749 venues, ~179s.
  SP3_data_sources.md's CBB section corrected to match. Phase 8 fully closed.
- Full production-DB historical backfill, 5 leagues (2026-07-12): the dev database had
  only single-recent-season sample data from Phase 5's browser walkthrough (not full
  history). Ran the real `import_historical` backfill for CFB/MLB/NFL/NBA/NHL into the
  actual persistent `backend/sports_passport.db` via 5 parallel background subagents
  (CBB skipped per user request). Final counts, all zero unmatched-team errors unless
  noted: **CFB 52,415** (1990-2025, 1,911 teams), **MLB 123,371** (1970-2025, 54 teams),
  **NBA 73,272** (1946-2025, 63 teams, matches the exact Phase 4 verification number),
  **NFL 7,276** (1999-2025, 35 teams), **NHL 57,395** (1970-2025, 62 teams, 3 benign
  errors — the known 2004-05 lockout gap plus two other seasons, 1990 and 2019, that
  came back with "no standings" from the API; worth a closer look later but games still
  imported in bulk for those years via the schedule endpoint, so likely just a standings
  *endpoint* miss on a couple of season-label edge cases, not a real backfill gap — not
  investigated further here). **313,729 games total** across the 5 leagues.
  - **Real gap found and fixed**: `backend/sports_passport/db/database.py` never had
    SQLite concurrency settings configured (WAL mode / busy_timeout), despite
    SP3_plan.md's risk table already claiming "WAL mode on (as in SP2)" — an apparent
    Phase 0 porting gap. Added an SQLAlchemy connect-event listener setting
    `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=30000`, which the live FastAPI
    app now benefits from for concurrent request handling. Caveat found the hard way
    during this backfill: that listener is bound to `database.py`'s specific `engine`
    object, so any script (like these verification scripts, or any future one-off admin
    script) that calls its own `create_engine(...)` instead of importing the real one
    doesn't get it — CFB and MLB each needed a retry after hitting "database is locked"
    under concurrent writes before an explicit `connect_args={'timeout': 30}` fixed it
    for good. Both retries were safe since `import_historical` is idempotent.
