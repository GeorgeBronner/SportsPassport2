# SportsPassport2 Build Plan — First Draft

Multi-league game attendance tracker (codename SP3 during planning; **the app keeps the name
SportsPassport2** and lives in `E:\Documents\Coding\myProjects\SportsPassport2`). Track games
attended across **College Football (CFB), MLB, NFL, NBA, and NHL**, extensible to future
leagues (MLS, etc.). Direct evolution of the original college football tracker (preserved at
`E:\Documents\Coding\myProjects\cfb-tracker`), reusing its proven stack and porting its CFB
integration. Phase progress is tracked in [tasks/todo.md](tasks/todo.md).

Companion doc: [SP3_data_sources.md](SP3_data_sources.md) — full data source research.

---

## 1. Goals & Scope (First Draft)

**In scope:**
- User accounts (email/password + JWT, same as SP2)
- Game database for 5 leagues: CFB (1990+), MLB/NFL/NBA/NHL (1970+)
- Mark games attended, with personal notes
- Stats dashboard: games by league, by team, by season, unique venues, states visited
- Admin: per-league data import + refresh
- Docker Compose deployment, single container, same as SP2

**Out of scope for first draft** (design for, don't build):
- MLS or other additional leagues
- Box scores / player stats (we only store teams, date, location, score + a few extras)
- Social features, sharing, photos
- Migration tool for existing SP2 attendance data (Phase 7 stretch goal)

**Data floor:** 1970 for the four pro leagues (sources support earlier — importers take a
`start_season` parameter so we can deepen later), 1990 for CFB (matches SP2 / CFBD coverage).
**Exception:** NFL ships with a 1999 floor (see §5 Phase 3) — the free nflverse source only
goes back that far; pre-1999 needs a Kaggle-gated dataset, deferred to Phase 7.

---

## 2. Tech Stack (carry over from SP2)

| Layer | Choice | Notes |
|-------|--------|-------|
| Backend | FastAPI + SQLAlchemy + Alembic + Pydantic | Identical to SP2 |
| DB | SQLite | ~320k game rows total (MLB ~130k, NBA ~70k, NHL ~60k, CFB ~40k, NFL ~15k) — well within SQLite comfort zone |
| Auth | JWT + bcrypt | Port from SP2 unchanged |
| Frontend | React 18 + TypeScript, Vite, Tailwind, React Router, Axios | Port SP2 frontend, add league dimension |
| Deploy | Docker + Docker Compose, frontend built to `backend/static/`, port 8000 | Same pattern; new container name |
| Package mgmt | uv (backend), npm (frontend) | Same as SP2 |

Repo/folder: `E:\Documents\Coding\myProjects\SportsPassport2` (fresh repo; the old app is
preserved at `cfb-tracker`). Backend package name: `sports_passport` (drop the sport-specific
`college_football_tracker` naming).

---

## 3. Data Model

Generalize SP2's schema; `league` becomes a first-class entity. Key change from SP2:
`api_game_id` becomes a **(source, source_game_id)** pair since each league has a different
upstream, and NFL/MLB historical rows come from CSVs without a native ID (we synthesize a
deterministic key, e.g. `date:away:home`).

```
leagues
  id, code ('CFB','MLB','NFL','NBA','NHL'), name, sport, active

teams
  id, league_id (FK), name, nickname, abbreviation,
  city, state, first_season, last_season (NULL = active),
  franchise_id (nullable — groups relocated/renamed teams: e.g. OAK/LA/LV Raiders),
  conference/division (nullable, CFB + pro),
  source, source_team_id (unique per source)

venues
  id, name, city, state, country, capacity (nullable),
  source, source_venue_id (nullable)

games
  id, league_id (FK), season, season_type ('regular'|'postseason'|'preseason'),
  week (nullable — NFL/CFB only), start_date (UTC; date-only OK for old games,
  has_time flag), home_team_id (FK), away_team_id (FK),
  home_score, away_score, venue_id (FK, nullable), neutral_site (bool),
  attendance (nullable), overtime_flag (nullable — OT/SO for NHL, extra innings for MLB),
  source, source_game_id  → UNIQUE(source, source_game_id)

users            — unchanged from SP2
user_game_attendance — unchanged from SP2 (user_id, game_id, notes, created_at)
```

**Design decisions baked in:**
- `franchise_id` solves the relocation problem (Montreal Expos → Washington Nationals,
  Seattle SuperSonics → OKC Thunder, Oakland/LA/LV Raiders…). First draft: populate teams as
  distinct rows per identity, group by franchise where the source makes it easy; stats
  default to team-as-listed with franchise rollup as a later enhancement.
- Venue is nullable because NBA historical data won't have it from the API. We ship a
  hand-built `data/nba_arenas.csv` (team → arena → season range) as seed data and join
  during import (see §5.4).
- All importers are **idempotent upserts** keyed on `(source, source_game_id)` — safe to
  re-run, same as SP2's refresh pattern.

---

## 4. Adapter Architecture

One module per league implementing a common interface. This is the core design decision that
makes MLS-later cheap.

```
sports_passport/
  services/
    adapters/
      base.py          # LeagueAdapter ABC
      cfb.py           # CollegeFootballData.com  (port of SP2 services/cfb_api.py)
      mlb.py           # Retrosheet bulk + MLB Stats API sync
      nfl.py           # Kaggle/Spreadspoke CSV bulk + nflverse games.csv sync
      nba.py           # bulk CSV or nba_api backfill + stats.nba.com sync
      nhl.py           # official NHL API (bulk + sync, same source)
    importer.py        # shared upsert/normalize logic (team matching, venue dedupe)
```

```python
class LeagueAdapter(ABC):
    league_code: str
    async def import_teams(self, db) -> ImportResult
    async def import_historical(self, db, start_season: int, end_season: int) -> ImportResult
    async def sync_recent(self, db, since: date) -> ImportResult   # the cheap daily/weekly call
```

`import_historical` reads **local bulk files first** (downloaded into `data/raw/<league>/`),
falling back to API pagination where the source is an API. `sync_recent` only ever touches
free APIs with tiny request counts.

### Per-league source wiring (from SP3_data_sources.md recommendations)

| League | `import_teams` | `import_historical` (one-time) | `sync_recent` (ongoing) |
|--------|----------------|-------------------------------|------------------------|
| **CFB** | CFBD `/teams/fbs` (API key, same as SP2) | CFBD `/games?year=` 1990→now (port SP2 code) | CFBD `/games?year={current}` |
| **MLB** | Retrosheet `CurrentNames.csv` (franchise-linked team-identity eras, back to 1871) | **Retrosheet game logs** ZIP, fetched live per season (1970+; has date, teams, score, park code, attendance, day/night). Park code → venue via `parkcode.txt` (has real city/state). Regular season only — see §5 Phase 3 scope note | **MLB Stats API** `/api/v1/schedule?startDate=&endDate=` — team resolved via its `teamCode` field, which matches Retrosheet's codes exactly, so sync rows land on the same games the bulk import created |
| **NFL** | nflverse `teams.csv` + franchise ids derived from `games.csv` team abbreviations | **nflverse `games.csv`** raw GitHub URL — plain HTTP GET, no key, auto-updated. 1999+ only (see §5 Phase 3 decision — Kaggle Spreadspoke would extend to 1966 but now needs a login/paid tier) | Same `games.csv` fetch, filtered by date |
| **NBA** | `stats.nba.com` teams endpoint + hand-curated historical teams | **`nba_api` LeagueGameFinder** season-by-season 1970→now with 1–2s sleep between requests (throttle-safe), OR Kaggle `Games.csv` as a fallback. Venue from our seed `nba_arenas.csv` | **`nba_api` scoreboard/gamefinder** for recent dates |
| **NHL** | NHL API `/v1/standings` + team endpoints | **Official NHL API** schedule endpoints, season-by-season 1970→now (keyless, official — no bulk concern) | Same NHL API, `/v1/score/{date}` |

**Compliance guardrails (from research — enforce in code):**
- MLB Stats API: *never* used for bulk backfill (terms are non-bulk). Retrosheet only.
- stats.nba.com: rate-limited backfill with sleeps + retry/backoff; run once, cache result.
- No Sports-Reference scraping anywhere.
- nflverse/Retrosheet/NHL API: no restrictions relevant to us.

**Python deps added over SP2:** `nba_api`, `pandas` (CSV wrangling for Retrosheet/Kaggle
files). MLB/NHL/nflverse are plain `httpx` calls — no extra deps.

---

## 5. Build Phases

### Phase 0 — Scaffold (½ day) ✅ DONE 2026-07-11
- [x] Create `SportsPassport2/` repo: copy cfb-tracker skeleton (backend layout, Dockerfile,
      docker-compose, alembic config, frontend scaffold), rename package to `sports_passport`
- [x] Strip CFB-specific naming from models/routers; keep auth (`core/security.py`,
      `routers/auth.py`), user model, test harness as-is
- [x] New CLAUDE.md (conventions carried from cfb-tracker)
- [x] Git init, initial commit on `main`
- **Verified:** full pytest suite green; uvicorn smoke test — /health, register, login,
  and /api/leagues all round-trip. (Docker build deferred to Phase 6; frontend still the
  unported cfb-tracker UI until Phase 5.)

### Phase 1 — Core schema + adapter framework (1 day) ✅ DONE 2026-07-11
- [x] Implement §3 models + Alembic initial migration (`9182bb4bc1d2`, applies cleanly)
- [x] `LeagueAdapter` ABC + `importer.py` shared upsert helpers
- [x] Seed `leagues` table at startup (CFB/MLB/NFL/NBA/NHL)
- [x] Admin router: `POST /api/admin/import/{league}/teams`,
      `POST /api/admin/import/{league}/historical?start_season=&end_season=`,
      `POST /api/admin/sync/{league}`, plus `GET /api/admin/status`
- [x] Games router: `GET /api/games?league=&season=&team=` with pagination; new `GET /api/leagues`
- **Verified:** 110 tests passing, including importer idempotency, cross-league
  source-id isolation, multi-league filters, and league-aware attendance stats.

### Phase 2 — First two adapters: NHL, then CFB (1–2 days) ✅ DONE 2026-07-11
Start with NHL (single official source for everything = simplest proof of the architecture),
then CFB (port of known-working SP2 code = validates parity with SP2).
- [x] NHL adapter (`adapters/nhl.py`): teams (62 all-time incl. defunct, with the API's own
      `franchiseId` mapped to our `franchise_id`), season backfill via standings +
      club-schedule-season with dedupe and 0.25s throttle, sync via `/v1/score/{date}`,
      OT/SO flags, venues from API (name-keyed; no city/state — enrich later)
- [x] CFB adapter (`adapters/cfb.py`): ported from cfb-tracker into adapter shape
- [x] CFB live verification: run a season import with a CFBD API key and compare counts
      against the cfb-tracker DB
- **Verified (NHL, live API 2026-07-11):** 2023-24 regular season = **1,312 games exact**;
  1993-94 = **1,092 exact** (26 teams × 84); 1994 SCF Game 7 present (VAN 2 @ NYR 3,
  Madison Square Garden); 1993-94 postseason = 90 games; 5 NHL adapter unit tests green
  (115 total).
- **Verified (CFB, live API 2026-07-11):** 2023 season import via `CfbAdapter.import_historical`
  against the real CFBD API = **3,734 games exact** (3,595 regular + 139 postseason), matching
  the old cfb-tracker DB (`cfb-tracker/data/college_football-11-15.2025.db`) row-for-row on both
  the total and the regular/postseason split. 1,911 teams and 841 venues imported (CFBD's
  `/teams` endpoints return all-time rosters, not season-scoped).

### Phase 3 — NFL + MLB adapters (1–2 days) ✅ DONE 2026-07-11
- [x] NFL adapter (`adapters/nfl.py`, source `nflverse`): historical + sync both read
      nflverse's `games.csv`/`teams.csv` directly (no local bulk file needed — the CSV is
      small and auto-updated). **Floor changed from 1970 to 1999** — see decision below.
- [x] MLB adapter (`adapters/mlb.py`, source `retrosheet` for bulk, MLB Stats API for sync):
      parses Retrosheet's fixed-field gamelog CSV (fetched live per season, not cached to
      `data/raw/` — same live-fetch pattern as CFB/NHL/NFL, since Retrosheet is a plain
      static host with no rate limit), franchise-links relocated teams via `CurrentNames.csv`
      column 1 (e.g. Expos→Nationals), and resolves park codes to venues (with real
      city/state, unlike NHL/NFL's name-only venues) via `parkcode.txt`.
- **Decision (2026-07-11):** the Kaggle "Spreadspoke" CSV that was supposed to cover NFL
  1966–1998 now sits behind a Kaggle login or a $24.99/yr paid tier (site changed since the
  original research pass) — not a plain HTTP fetch. User chose to ship NFL on nflverse alone
  (auth-free, auto-updated) with a **1999 floor** instead of blocking on Kaggle access;
  1970–1998 backfill is deferred, revisit if a free source appears (Phase 7 candidate).
- **Verified (NFL, live nflverse fetch 2026-07-11):** 1999 season = **259 games exact** (248
  regular + 11 postseason, 1999's single-bye 31-team format); 2020 = **269 exact** (256 + 13,
  expanded playoff format); 2023 = **285 exact** (272 + 13, 17-game regular season). Franchise
  linking verified: STL Rams (1999–2015) and LA Rams (2016–) share `franchise_id` 2510 from
  nflverse's stable `nfl_team_id`. Super Bowl XXXIV score double-checked against the real
  result (Rams 23, Titans 16) — exact match. 5 NFL adapter unit tests green (120 total).
- **Verified (MLB, live Retrosheet + MLB Stats API fetch 2026-07-11):** 1970 season = **1,944
  games exact** (24 teams × 162 / 2), zero unmatched-team errors; 2024 season = **2,429 games**
  via Retrosheet. 1970 opening-day score double-checked (Tigers 5, Senators 0 at RFK Stadium,
  attendance 45,015 — exact match). Franchise linking verified (Expos→Nationals share
  `franchise_id`). Cross-source id alignment tested: MLB Stats API's `teamCode` field matches
  Retrosheet's team codes exactly (verified against all 30 current teams), so `sync_recent`
  resolves onto the *same* game rows the bulk import created — spot-checked a 10-day window
  in the 2024 season, 130/132 games matched cleanly (2 edge-case mismatches, likely
  rescheduled games — acceptable for a hobby tracker). 4 MLB adapter unit tests green
  (124 total).
- **Scope note:** Retrosheet's gamelogs are regular-season only; MLB postseason isn't backed
  by a simple CSV on their site (would need real scraping) and is deferred — sync_recent will
  pick up *future* postseason games automatically once they happen, just not historical ones.

### Phase 4 — NBA adapter (1 day; the fiddly one)
- [ ] Build `data/seed/nba_arenas.csv` (team, arena, city, state, first_season, last_season)
      — one-time research task, ~120 rows
- [ ] NBA adapter: `nba_api` LeagueGameFinder backfill with throttling (or Kaggle CSV if
      throttling proves painful), join arenas seed for venue, wire sync
- **Verify:** NBA 2023-24 = 1,230 regular season games; verify arena joins produce a venue
  for >95% of games 1970+

### Phase 5 — Frontend (2–3 days)
Port SP2 frontend and add the league dimension:
- [ ] League switcher (top-level nav or filter chip row) + "All leagues" view
- [ ] Game search/browse: league, season, team, date filters; mark-attended flow (same UX as SP2)
- [ ] Stats dashboard: totals by league; games by team, by season; unique venues; states
      visited; per-league passport "completion" (venues visited / active venues)
- [ ] Team pages aware of franchise history where populated
- **Verify:** manual walkthrough — register, mark games attended in ≥3 leagues, confirm all
  dashboard numbers by hand against the DB

### Phase 6 — Sync scheduling + deploy (½–1 day)
- [ ] Nightly sync job (APScheduler in-process, matching SP2's simplicity; per-league
      enable/disable in admin). In-season leagues only — sync no-ops out of season
- [ ] Admin UI: per-league import status, last-sync timestamp, row counts
- [ ] Deploy via Docker Compose; document in `docs/deployment.md`
- **Verify:** force a sync, confirm yesterday's real scores appear; restart container,
      confirm scheduler resumes

### Phase 7 — Stretch (post-first-draft)
- [ ] SP2 attendance migration script (SP2 SQLite → SP3, matching games on date+teams)
- [ ] Franchise rollup stats; MLS adapter (ESPN/TheSportsDB per research); deepen history pre-1970

**Total estimate: ~7–10 working days** for the first draft (Phases 0–6).

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Team name matching across sources (e.g., Retrosheet codes vs MLB API names) | Per-adapter alias tables in `data/seed/<league>_team_aliases.csv`; import fails loudly on unmatched teams rather than silently creating dupes |
| stats.nba.com blocks the backfill | Fallback already chosen: Kaggle bulk CSV; backfill is one-time so even a slow crawl is acceptable |
| Kaggle files need manual download (auth) | Hit for NFL 1966–1998 backfill; resolved by dropping that range (1999 floor via nflverse) rather than requiring a Kaggle account. Revisit if a free 1970–1998 source turns up |
| nflverse/Kaggle schema drift | Importers validate expected columns before ingesting; sync failures surface in admin UI, never corrupt data (upserts are transactional) |
| ESPN-style unofficial APIs breaking | Not load-bearing in this plan — NBA (`stats.nba.com`) is the only unofficial dependency, with a bulk-CSV escape hatch |
| SQLite write contention during big imports | Imports are admin-triggered and sequential; WAL mode on (as in SP2) |

## 7. Decisions Already Made (don't re-litigate during build)

1. Reuse SP2 stack wholesale — this is an evolution, not a rewrite.
2. League adapters + common `games` schema is the extensibility mechanism.
3. Free sources only; no paid API in the first draft. Paid fallbacks documented in
   SP3_data_sources.md if a free source dies.
4. Bulk files for backfill, APIs for sync — never bulk-crawl a rate-limited/ToS-restricted API.
5. 1970 floor for pro leagues, 1990 for CFB; `start_season` parameterized for later deepening.
6. Venue completeness target: MLB/NFL/NHL/CFB from source data; NBA via hand-built seed file.
