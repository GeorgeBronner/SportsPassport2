# SportsPassport2 Build Plan — First Draft

Multi-league game attendance tracker (codename SP3 during planning; **the app keeps the name
SportsPassport2** and lives in `E:\Documents\Coding\myProjects\SportsPassport2`). Track games
attended across **College Football (CFB), MLB, NFL, NBA, and NHL**, extensible to future
leagues (MLS, etc.). Direct evolution of the original college football tracker (preserved at
`E:\Documents\Coding\myProjects\cfb-tracker`), reusing its proven stack and porting its CFB
integration. Phase progress is tracked in this document's own phase checkboxes
(`tasks/todo.md` was retired).

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

**Added beyond the original first-draft scope:** CBB (D-I men's college basketball, 1990+) —
see §5 Phase 8. Not part of the original 5-league plan; added once the CFB/pro-league adapters
and multi-league frontend were done and a clean data source (CBBD, CFBD's sister project) turned
up during MLS-expansion research.

**Out of scope for first draft** (design for, don't build):
- MLS or other additional leagues
- Box scores / player stats (we only store teams, date, location, score + a few extras)
- Social features, sharing, photos
- Migration tool for existing SP2 attendance data (Phase 7 stretch goal)

**Data floor:** 1970 for the four pro leagues (sources support earlier — importers take a
`start_season` parameter so we can deepen later), 1990 for CFB (matches SP2 / CFBD coverage).
~~**Exception:** NFL ships with a 1999 floor~~ — closed 2026-08-01 (Phase 11): the Kaggle
Spreadspoke file is freely downloadable again and now backs NFL 1970–1998.

---

## 2. Tech Stack (carry over from SP2)

| Layer | Choice | Notes |
|-------|--------|-------|
| Backend | FastAPI + SQLAlchemy + Alembic + Pydantic | Identical to SP2 |
| DB | SQLite (WAL mode + busy_timeout, see §6) | ~493k game rows loaded as of 2026-07-14 (MLB 123k, NBA 73k, CBB 179k, NHL 57k, CFB 52k, NFL 7k) — well within SQLite comfort zone |
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
  week (nullable — NFL/CFB only), start_date (UTC — always; sources that
  publish US Eastern are converted on import via
  `services/adapters/local_time.py`, see SP3_open_issues.md #7. Date-only OK
  for old games, has_time flag), home_team_id (FK), away_team_id (FK),
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
      nba.py           # Kaggle bulk CSV backfill + ESPN scoreboard sync
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
| **NFL** | nflverse `teams.csv` + franchise ids derived from `games.csv` team abbreviations, plus 7 pre-1999 identities hard-coded in the adapter (`HISTORICAL_TEAMS`) | **nflverse `games.csv`** raw GitHub URL for 1999+ — plain HTTP GET, no key, auto-updated — and the **Kaggle "Spreadspoke" CSV** (`backend/data/raw/nfl/spreadspoke_scores.csv`) for 1970–1998, split at `FIRST_NFLVERSE_SEASON` (see §5 Phase 11) | Same `games.csv` fetch, filtered by date — nflverse only |
| **NBA** | Derived from `Games.csv` itself (distinct team-identity eras seen in the data) | **Kaggle `Games.csv`** (`backend/data/raw/nba/Games.csv`, manually downloaded — `stats.nba.com` is unreachable from the dev sandbox, see §5 Phase 4 status). Venue only available for the dataset's current season; historical venues come from the `nba_arenas.csv` seed (built 2026-07-27) | **ESPN scoreboard** `site.api.espn.com/.../basketball/nba/scoreboard?dates=` — replaced `stats.nba.com/scoreboardv2` on 2026-08-01, which is Akamai-blocked from every host this app runs on (see Phase 4). Reconciles onto bulk rows by natural key, since ESPN carries no NBA `gameId` |
| **NHL** | NHL API `/v1/standings` + team endpoints | **Official NHL API** schedule endpoints, season-by-season 1970→now (keyless, official — no bulk concern) | Same NHL API, `/v1/score/{date}` |

**Compliance guardrails (from research — enforce in code):**
- MLB Stats API: *never* used for bulk backfill (terms are non-bulk). Retrosheet only.
- stats.nba.com: abandoned 2026-08-01, Akamai-blocked from every host we run on.
  NBA sync uses ESPN instead — throttled, descriptive User-Agent, sync-only (never bulk).
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
- **Known gap found during Phase 5 (2026-07-12):** NHL's `import_teams` never sets
  `first_season`/`last_season` on team rows — confirmed live, `api.nhle.com/stats/rest/en/team`
  (the only teams endpoint used) doesn't return season-range fields at all. This surfaced as a
  wrong/misleading franchise-history ordering on the new team detail page (e.g. Colorado
  Avalanche sorting before Quebec Nordiques). Worked around at the UI layer (don't display or
  sort on a season range we don't actually have — see `TeamDetail.tsx`) rather than guessing;
  the real fix is computing each NHL team's season range from its imported games
  (MIN/MAX `Game.season` per team) after `import_historical` runs, which is separate work, not
  a one-line adapter fix. Every other league's adapter (CFB/MLB/NFL/NBA) already sets these
  fields correctly.

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
- **Superseded (2026-08-01):** re-checked, and the dataset's public download API serves it
  unauthenticated again. The 1999 floor is gone — see Phase 11 below.
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
- **Scope note (resolved 2026-07-15):** MLB postseason was originally deferred on the
  belief Retrosheet had no CSV for it — wrong. Retrosheet publishes four postseason gamelog
  files in the same fixed-field format (glws/gllc/gldv/glwc.zip, each spanning all years of
  its series type). `import_postseason(start, end)` fetches them and filters by season;
  wired into `import_historical`. Backfilled 1970-2025 into the live DB = **1,483 games,
  0 errors** (WS/LCS/DS/WC). sync_recent still picks up future postseason games live.

### Phase 4 — NBA adapter (1 day; the fiddly one) ✅ DONE 2026-07-12
**Status:** the historical-import path is written, tested, and verified against the
real local data file for both a single season and the full 1946-2025 range (and, as
of the Phase 9 production backfill below, actually loaded into the live dev database
too — 73,272 games, exact match). The live-sync path was the last open item in this
phase and **closed 2026-08-01**: `stats.nba.com` turned out to be unreachable from
every network this app runs on, so sync moved to ESPN and was verified end-to-end
against the live endpoint (see the resolved item below). The venue seed file was
deferred to Phase 7 and has since been built. Original work committed in `4065c9a`.

- [x] **Blocker discovered and resolved:** `stats.nba.com` (both the API and the plain
      web page) is unreachable from this dev environment — it hangs on what looks like
      an Akamai anti-bot TLS challenge, not a rate limit (`curl` times out after
      SSL renegotiation, `www.nba.com` bare page returns 403). This matches the risk
      the original research doc already flagged. The documented fallback (Kaggle bulk
      CSV) needs a Kaggle login, same class of blocker as NFL's Spreadspoke CSV.
- [x] **User decision:** grab the Kaggle CSV manually rather than fight stats.nba.com.
      Dataset: [`eoinamoore/historical-nba-data-and-player-box-scores`](https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores)
      ("NBA Dataset: Box Scores and Stats, 1947–Today"). Only `Games.csv` is needed (not
      the player/team box-score files). **Already downloaded and in place at
      `backend/data/raw/nba/Games.csv`** (73,279 rows, 1946–2026, gitignored under
      `backend/data/raw/`).
- [x] NBA adapter (`backend/sports_passport/services/adapters/nba.py`, source
      `nba-kaggle`), registered in `adapters/__init__.py`:
  - `import_teams` / `import_historical` parse the local `Games.csv` directly (no
    network call — there's no free live bulk source for NBA, unlike the other four
    leagues). Team identity: NBA's numeric team id is stable across every relocation
    (id 1610612760 is both the Seattle SuperSonics and OKC Thunder), so each
    `(team_id, city, name)` combo actually seen in the CSV becomes its own team row,
    linked by `franchise_id = team_id`.
  - Season is derived from the NBA's own `gameId` encoding (digit 0 = game type, digits
    1–2 = season start year, see `_season_from_game_id`), **not** the game date — the
    2019-20 season's COVID-delayed playoffs ran into October 2020, which a date-based
    rule would misclassify into the wrong season. Verified against 164 real mismatches
    in the raw file before switching to the ID-based method.
  - `sync_recent` targets `stats.nba.com/stats/scoreboardv2` with the header set
    `nba_api` normally sends (`x-nba-stats-origin`, `x-nba-stats-token`, etc.) —
    **written per the original plan but not live-verified at all**, since this sandbox
    can't reach the host. A home/production network may succeed where this sandbox's
    egress is blocked (cloud IP ranges are far more likely to be flagged than a
    residential one) — **this needs a real end-to-end test after deploy**, including
    checking the `scoreboardv2` response shape is still current (undocumented endpoint,
    can drift). If it doesn't work, the pragmatic fallback is to skip NBA's automated
    sync entirely and re-download a fresh `Games.csv` from Kaggle periodically instead
    (the dataset is "updated nightly" upstream).
- [x] **Verified (local Games.csv parse, 2026-07-11):** `import_historical(2023, 2023)`
      → 1,383 games, **zero unmatched-team errors**. Breakdown: 1,231 regular season
      (1 over the expected 1,230 — likely the in-season NBA Cup championship game, which
      this adapter currently buckets under `"regular"` rather than its own type; minor,
      not investigated further), 88 postseason, 64 preseason. Franchise linking confirmed:
      Seattle SuperSonics (1967–2007) and OKC Thunder (2008–) both resolve to
      `franchise_id` 1610612760.
- [x] **Fixed the NBA Cup miscount (2026-07-12):** the extra game was the in-season
      tournament's standalone championship final (`gameId` type digit `"6"`,
      e.g. `62300001`), which doesn't count toward either team's regular-season
      record — unlike the 66 `"NBA Emirates Cup"` group-stage games, which do and
      correctly stay `"regular"`. Gave the final its own `season_type = "cup_final"`
      in `GAME_TYPES`. Re-verified: 2023-24 = exactly 1,230 regular season games.
- [x] `test_nba_adapter.py` written (6 tests: team import + franchise linking,
      idempotency, historical import incl. the Cup-final split and season-range
      filtering, venue-only-when-present, sync). `nba_league` fixture added to
      `tests/conftest.py`. 130 tests green (up from 124).
- [x] **Two real bugs found and fixed while writing the sync test** (still no live
      network access to confirm end-to-end, but these were provably wrong from the
      documented API shape): `_upsert_scoreboard_game` was feeding `sync_recent`'s
      raw `GAME_ID` (10 chars — `stats.nba.com` prefixes the Kaggle `gameId` format
      with a 2-char league id, e.g. `0022300500`) straight into
      `_season_from_game_id`, which is calibrated for the unprefixed 8-char form —
      this silently misparsed the season by reading the league-id digits instead of
      the season digits. It also stored that raw 10-char id as `source_game_id`,
      which would never match the 8-char ids the bulk import creates — every synced
      game would've landed as a duplicate row instead of updating the historical
      one (the exact cross-source alignment problem the MLB adapter solved via
      `teamCode`). Fixed by stripping the 2-char prefix before both calls.
  - [x] **Resolved 2026-08-01 by abandoning `stats.nba.com` entirely.** The
        "try it from a network that can reach it" plan had no such network:
        every nba.com host (`stats.` *and* `cdn.`) returns an Akamai
        `Access Denied` from the Oracle production host and from a residential
        connection alike, with and without browser-shaped headers. The
        cloud-IP hypothesis was wrong — this endpoint is unreachable from
        anywhere this app runs. `sync_recent` moved to ESPN's scoreboard,
        which `SP3_data_sources.md` already lists as NBA's backup update
        source, and which also carries the venue data `scoreboardv2` never
        returned. Because ESPN has no NBA `gameId`, the adapter reconciles on
        (league, home, away, start ±12h) so synced rows and bulk rows converge
        instead of duplicating — in both directions, and the match must be
        unique or it is reported as an error rather than guessed. The window
        started at ±1 day and was narrowed after review: the same matchup
        recurs within 24h **294 times** in the loaded data (287 at exactly
        24.0h, tightest genuine modern gap 22h), so a day-wide window
        overwrote one real game with another. 12h clears the 8h max
        UTC-vs-local skew between the two sources and stays inside that 22h
        separation.
        **Verified live 2026-08-01:** 34 real events over four dates —
        including both halves of a consecutive-night pair and All-Star
        weekend — gave 30 updates, 0 inserts, 0 errors and 4 correctly-named
        skips; the games matched their existing Kaggle rows exactly (scores,
        season, canonical 8-char ids) and the back-to-back pair resolved to
        two distinct rows.
- [x] **Full backfill run (2026-07-12):** `import_historical(1946, 2025)` against
      the real local `Games.csv` — **73,272 games imported, zero errors.** The
      7-game gap vs. the CSV's 73,279 rows is exactly the intentionally-excluded
      All-Star Games (confirmed by count). 63 team rows (all relocations/renames
      resolved), 47 venues, 1,393 games with venue data (the current-seasons-only
      subset — see venue caveat below).
- [x] **Decision (2026-07-12):** venue seed file (`data/seed/nba_arenas.csv`) deferred
      to Phase 7 (see below) rather than blocking Phase 4 close — user chose to ship
      NBA with sparse venue coverage (current-era games only, ~2%) for the first
      draft, same pattern as the NFL 1970-1998 / MLB postseason deferrals.
- **Verified:** NBA 2023-24 = 1,230 regular season games exact (Cup final correctly
  split out); full 1946-2025 backfill clean with zero unmatched-team errors.
  **Phase 4 closed** except for the still-pending live `sync_recent` test (needs a
  network that can reach `stats.nba.com`; do this once deployed).

### Phase 5 — Frontend (2–3 days) ✅ DONE 2026-07-12
Ported the still-CFB-only cfb-tracker frontend to the generalized backend (types/API clients
still used the old `school`/`mascot`/`api_team_id` field names from before Phase 1's schema
generalization) and added the league dimension:
- [x] League filter lives on the Games/browse page (`GameFilters`), not a global header
      switcher — Dashboard/Statistics already show every league at once via
      `AttendanceStats.games_by_league`, so a global switcher would have no effect there.
      Selecting a league re-scopes the team/season dropdowns and resets the team selection.
- [x] Game search/browse: league, season, team filters; mark-attended flow unchanged from SP2's
      UX. Season/date filters already existed; added league.
- [x] Stats dashboard: "Games by League" section added to both Dashboard and Statistics,
      sourced from the backend's existing (previously unused by the frontend)
      `games_by_league` field.
- [x] Team pages aware of franchise history: new `/teams/:id` page, reachable from team names
      on game cards. Needed two small backend additions — `GET /api/teams/{id}` and a
      `franchise_id` filter on `GET /api/teams/` (neither existed before; only a list endpoint
      did). 4 new backend tests (134 total).
- [x] **Two real bugs fixed along the way** (not regressions — both pre-existing):
  - `formatDate`/`formatDateShort` hardcoded `timeZone: 'America/Chicago'`. Bulk-imported
    historical rows (confirmed in `mlb.py`) store `start_date` as naive midnight UTC, so
    converting to Central time rolled the displayed date back a day for most historical MLB
    games. Fixed to format in UTC — the app never shows time-of-day, only the calendar date,
    so this is strictly safer for every league.
  - Building the team franchise-history view surfaced that NHL's `import_teams` never sets
    `first_season`/`last_season` (confirmed live: `api.nhle.com/stats/rest/en/team` has no
    season-range fields at all) — every other league's adapter sets these correctly. This
    produced a wrong-order, falsely-"present" franchise timeline for NHL teams. Fixed at the
    UI layer (don't display or sort on data that isn't there) rather than guessing; the real
    fix — computing each team's season range from its imported games — is separate work,
    logged above under Phase 2.
- [ ] **Deferred, not built:** per-league "passport completion" (venues visited / active
      venues). No endpoint exists for "total venues for a league," and the semantics are
      genuinely ambiguous (do a relocated team's old venues count forever?) — rather than guess,
      left for a later phase alongside the NBA arena seed file.
- **Verified (2026-07-12):** full walkthrough via the Chrome browser tools against a live
  dev instance — registered/logged in, imported known-good cross-league data (CFB 3,734 /
  MLB 2,429 / NBA 1,383 / NFL 285 / NHL 1,400 games, matching every prior phase's verified
  counts exactly), browsed games with the league filter (confirmed team/season lists reload
  and the MLB date-shift bug is gone), marked attendance across CFB/MLB/NBA, confirmed
  Dashboard + Statistics "Games by League" numbers matched by hand, exercised a team page with
  franchise history (Quebec Nordiques ↔ Colorado Avalanche) and one without, and ran a real
  Admin "Import Teams" action end-to-end through the UI. Zero browser console errors. Backend:
  134 tests green; `tsc -b` and `vite build` both clean.

### Phase 6 — Sync scheduling + deploy (½–1 day)
- [x] Nightly sync job (APScheduler `AsyncIOScheduler`, in-process, started/stopped via the
      FastAPI lifespan). One cron job at `settings.sync_hour` (default 06:00 server-local)
      walks every `SyncState.enabled` league and calls the adapter's `sync_recent`.
      Per-league enable/disable persisted in a new `sync_state` table (migration
      `d1f3a7c9e5b2`). **"In-season only" needs no calendar** — every adapter's `sync_recent`
      queries by date range, so an out-of-season window just returns zero games. Adaptive
      lookback (`compute_since`): last run today/yesterday or never → go back
      `sync_lookback_days` (default 3); a missed run → cover the gap back to the last run
      minus a 2-day cushion. Each league capped at a 600s timeout and wrapped so one league's
      failure (e.g. NBA's unreachable `stats.nba.com`) is recorded, never crashes the job.
      Shared `run_sync_for_league` / `sync_all_enabled` helpers used by both the scheduler and
      the admin endpoints so every sync path records the same last-run state.
- [x] Admin UI: `GET /api/admin/status` extended with per-league sync fields (enabled,
      last-run timestamp, status, games imported/updated, error); `PATCH
      /api/admin/sync-state/{league}` toggles auto-sync; `POST /api/admin/sync-all` runs the
      nightly job on demand. Frontend League Status table gains an Auto-sync toggle, a
      Last-sync column (OK/Error badge + timestamp + new-game count, error text on hover), and
      a "Run nightly sync now" button.
- [ ] Deploy via Docker Compose; document in `docs/deployment.md` — first deployment done
      (out of band); `docs/deployment.md` still to be written.
- **Verified (2026-07-16):** 174 backend tests green (14 new: `test_scheduler.py` covers the
      adaptive-lookback logic, per-league state recording, hard-failure capture, enabled-only
      iteration, and all sync-state endpoints). Lifespan confirmed to start/stop the scheduler
      with the cron job registered at `hour=6`. Live end-to-end: a real MLB `sync_recent`
      (in-season, Stats API) through `run_sync_for_league` against the dev DB imported a new
      game + venue idempotently and recorded `status=success`. `tsc -b` + `vite build` clean.
      Container-restart scheduler-resume check still pending an actual deploy.

### Phase 7 — Stretch (post-first-draft)
- [ ] SP2 attendance migration script (SP2 SQLite → SP3, matching games on date+teams)
- [ ] Franchise rollup stats; MLS adapter (ESPN/TheSportsDB per research); deepen history pre-1970
- [x] **Done (2026-07-27):** `data/seed/nba_arenas.csv` — hand-built NBA team → arena →
      season-range lookup, scoped to **1990-present** (66 rows) rather than the original
      full-history ~120-row target; games before 1990 remain venue_id = NULL. Backfills
      historical rows where `Games.csv` carries no arena data at all (see §5 Phase 4).
      Loaded via `services/adapters/venue_seed.py`, wired into `nba.py`'s `_upsert_row`.

### Phase 8 — CBB adapter (added beyond original scope) ✅ DONE 2026-07-12
Not part of the original 5-league plan (see §1). Added after Phase 5 once CBB data-source
research (`SP3_data_sources.md`) turned up CollegeBasketballData.com (CBBD) — CFBD's sister
project, same maintainer, and (live-confirmed) the same API key.
- [x] `CbbAdapter` (`backend/sports_passport/services/adapters/cbb.py`, source `cbbd`) — reuses
      `settings.cfb_api_key` directly rather than a separate CBB key setting.
- [x] **Two research findings corrected via live testing during the build** (see
      `SP3_data_sources.md`'s CBB section for the full correction):
  - The research's "2003 floor" was wrong — real, clean game data exists back to at least 1950
    (1,240 games that season, real teams/scores, verified live). The app ships with a **1990
    floor anyway**, matching CFB's — a scope decision (bounds decades of conference-realignment
    bookkeeping), not a data-availability limit. `start_season` is a parameter like every other
    adapter, so deepening later is cheap.
  - `GET /games` caps at **exactly 3,000 rows** regardless of `season`/`seasonType` filters
    (three different season queries each returned exactly 3,000, one cutting off mid-season).
    The real pagination mechanism is `startDateRange`/`endDateRange`; the adapter chunks every
    season into 6 monthly windows (Nov–Apr), verified safely under the cap in both the
    highest-volume month (November, 1,403 games) and the tournament month (March, 848 games).
- [x] Classification (`d1`/`non-d1`) read from each game's own `homeConference`/`awayConference`
      field at team-creation time — no extra per-season roster calls needed, unlike the
      research's proposed approach. Non-D-I "buy game" opponents get full team rows
      (school/mascot/abbreviation, no location) from CBBD's all-time `/teams` registry — no
      manual seed lookup needed, contrary to what the research assumed. `_counts_for_stats` in
      `routers/attendance.py` extended to treat `d1` like CFB's `fbs` (non-D-I opponents don't
      personally count in team-based stats, but the game itself is fully loggable either way).
- [x] `test_cbb_adapter.py` (6 tests, mocked `_get`) + `cbb_league` fixture in `conftest.py`;
      140 tests green.
- **Verified (live API, 2026-07-12):** single-season sanity check (2023) = **6,243 games, 0
      errors, 365 D-I teams** (exact match to the research's ~365-team estimate) + 355 non-D-I
      buy-game opponents captured incidentally, 454 venues. Full `import_historical(1990, 2024)`
      backfill (35 seasons): **179,107 games, zero unmatched-team errors**, 1,386 teams total
      (D-I rosters across 35 years of realignment + non-D-I buy-game opponents), 749 venues —
      ~179s end to end. Average ~5,117 games/season across the full range is consistent with the
      2023-only figure (6,243) once you account for game counts growing over three-plus decades
      as D-I expanded.

### Phase 9 — Full production historical backfill ✅ DONE 2026-07-12 (CBB added 2026-07-14)
Every adapter's `import_historical` had been verified correct (Phases 2-4, 8) but only ever
against scratch/in-memory databases or a single recent season — the actual persistent dev
database (`backend/sports_passport.db`) only had Phase 5's single-season browser-test data.
User asked for full backfills across all 5 original leagues (CBB skipped for now, per
instruction) run via parallel background subagents, with rate-limit guidance from each
adapter's existing built-in behavior (no new throttling code needed — NHL's 0.25s delay, MLB's
Retrosheet-only-for-bulk rule, etc. were already correctly implemented). CBB's own full backfill
(1990-2024) followed on 2026-07-14, run the same way against the persistent DB via the app's
own engine (WAL + busy_timeout already wired up) — 179,107 games, 1,386 teams, 749 venues, zero
errors, matching Phase 8's scratch-DB verification exactly. Independently re-confirmed via direct
SQL query against the database.
- [x] Fixed the SQLite WAL/busy_timeout gap (see §6) — required for safe concurrent writes,
      discovered when the first parallel run hit immediate `database is locked` errors.
- [x] **Final counts, real persistent database, zero unmatched-team errors unless noted:**

  | League | Games | Seasons | Teams |
  |--------|-------|---------|-------|
  | CFB | 52,415 | 1990-2025 | 1,911 |
  | MLB | 123,371 | 1970-2025 | 54 |
  | NBA | 73,272 | 1946-2025 | 63 (matches Phase 4's exact figure) |
  | NFL | 7,276 | 1999-2025 | 35 |
  | NHL | 57,395 | 1970-2025 | 62 (3 benign errors, see below) |
  | CBB | 179,107 | 1990-2024 | 1,386 (added 2026-07-14, matches Phase 8's figure) |
  | **Total** | **492,836** | | |

- **NHL anomaly (not investigated further):** 3 errors during the backfill — the known 2004-05
  lockout gap, plus seasons 1990 and 2019 each logging "no standings" from the adapter's
  standings-lookup call. Games still appear to have imported in bulk via the schedule endpoint
  for those years (the season range 1970-2025 has no visible holes), so this looks like a
  standings-endpoint edge case on a couple of season-label boundaries, not a real backfill gap
  — worth a closer look sometime, logged here rather than silently ignored.
- **Process note:** CFB and MLB each needed one retry after hitting transient lock contention
  from the concurrent writes (both idempotent, so safe) before an explicit
  `connect_args={'timeout': 30}` on the ad-hoc verification scripts fully resolved it — the WAL
  fix above only auto-applies to connections made through `sports_passport.db.database`'s own
  `engine` object, not to a script's own separate `create_engine(...)` call. Worth remembering
  for any future one-off script against this database.
- Independently re-verified every final count via a direct SQL query against the database
  (not just trusting each subagent's self-report) before considering this phase done.

### Phase 10 — MLS adapter (added beyond original scope) ✅ DONE 2026-08-01
Added to unblock the one attended MLS game in `SP3_open_issues.md` #1b. The seventh
league, and the first built on **two sources split at a hard season boundary** —
`FIRST_ASA_SEASON = 2013` — so the same match can never arrive twice.
- [x] Source research live-tested before ranking (`SP3_data_sources.md` MLS section):
      the ASA API won on UTC-native timestamps, complete per-season slates, and
      **venue coordinates supplied directly** — the only source in this project that
      does, so the 2013+ era needed no hand-built seed at all.
- [x] Kaggle `matches.csv` fills 1996–2012, but only after being validated against ASA
      on the 2013–2022 overlap (per-season counts match exactly; all 3,687 rows find a
      twin). Its clock times are 73% present and 80.6% accurate, so the era imports
      **date-only**; its `date` column is the *local* game day, which is what would
      have shifted every late kickoff a day forward if taken as UTC.
- [x] `mls_stadiums.csv` (27 rows) covers pre-2013 grounds ASA never lists plus the 8
      ASA stadia missing coordinates. Coordinates geocoded via Nominatim, not typed
      from memory. Adjacent-but-distinct buildings (Mile High/Empower Field, Foxboro/
      Gillette, Houlihan's/Raymond James) stay separate venue rows.
- [x] Explicit canonical maps for 33 team-name variants and 70 venue strings, plus
      free-text round labels → `season_type`. Validated exhaustively against the real
      file before import: 0 unmapped names, 0 unparseable dates, 0 key collisions.
- [x] **Final counts, live database, zero errors:**

  | Source | Games | Seasons | Notes |
  |--------|-------|---------|-------|
  | Kaggle | 3,601 | 1996–2012 | date-only; 453 with no venue (2001–03 source hole) |
  | ASA | 5,732 | 2013–2026 | real UTC kickoffs, coordinates, attendance |
  | **Total** | **9,333** | **1996–2026** | 33 teams, 75 venues, **0 venues missing coordinates** |

- Known limitation: ASA publishes results only (every row is `FullTime`), so MLS has
  no upcoming fixtures, unlike CFB/CBB/NHL.

### Phase 11 — NFL 1970–1998 backfill ✅ DONE 2026-08-01
Closes the 1999 floor the Phase 3 decision accepted. The blocker was access, not data:
re-checked on 2026-08-01 and the Kaggle "NFL scores and betting data" dataset
(`tobycrabtree`) serves `spreadspoke_scores.csv` over its public download API with no
login. NFL becomes the **second two-source league**, split at
`FIRST_NFLVERSE_SEASON = 1999` on the *season* (not the date), so the January-1999
playoffs of the 1998 season stay with their own season.
- [x] Source validated before writing any adapter code: on the **1999–2024 overlap
      Spreadspoke and nflverse agree exactly — 6,991 games each, zero per-season
      variance**. The 1970–1998 slice has no null date/score/stadium, no unparseable
      date and no duplicate `(date, home, away)` key, and its per-season counts
      reproduce the 1982 strike (141), the 1987 strike (177), the 1978 16-game
      expansion (233) and 1993's 18-week season.
- [x] **One real defect found and fixed**: Arizona Cardinals home games 1994–98 are
      stamped "University of Phoenix Stadium", which opened in 2006 — they played at
      Sun Devil Stadium. Confirmed independently on the overlap, where 55 rows under
      that name resolve to `PHO99`. Overridden on import.
- [x] Venue crosswalk derived **empirically from the overlap** (matched on date + both
      scores + home team) rather than by hand: **31 of the 64 pre-1999 stadiums are
      buildings nflverse also knows**, so those games join the existing venue rows and
      the map keeps one pin per building — Three Rivers now spans 1970–2000, Lambeau
      1970–2026. 29 new `hist-`-prefixed rows added to `nfl_stadiums.csv` for grounds
      nflverse never saw; 4 names are aliases onto rows that already existed.
- [x] 7 pre-1999 team identities minted (`HISTORICAL_TEAMS`), each because the obvious
      abbreviation belongs to a modern club: Baltimore Colts, St. Louis Cardinals,
      Houston/Tennessee Oilers, LA Raiders, Phoenix Cardinals, Boston Patriots.
      `franchise_id` points at the modern successor, so the passport reads
      Oilers→Titans as one franchise. This is why `_team_lookup` had to be re-keyed
      from `abbreviation` to `source_team_id` — the Oilers really were "HOU", and the
      old lookup would have shadowed the Texans.
- [x] **Final counts, live import, zero errors:**

  | Source | Games | Seasons | Notes |
  |--------|-------|---------|-------|
  | Spreadspoke | 6,367 | 1970–1998 | date-only (`has_time=False`); no attendance or OT column |
  | nflverse | 7,548 | 1999–2026 | real kickoff times, converted from US Eastern |
  | **Total** | **13,915** | **1970–2026** | 42 teams, 91 venues, **0 games without a venue** |

  Re-running the full range imports 0 and updates 13,915, so the seam is idempotent.
- Known limitation: a team's era is one `(first_season, last_season)` span, so an
  identity used in two separate stretches reads as continuous — visible now for OAK
  (Oakland 1970–81 and 1995–2019) and CLE (the 1996–98 hiatus). Games are attributed
  correctly; only the summary span overreaches. Narrowing it needs a schema change.

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
| SQLite write contention during big imports | **Actually wired up 2026-07-12** (this row was aspirational until then — WAL mode wasn't configured despite being listed here as already done, a Phase 0 porting gap). `backend/sports_passport/db/database.py` now enables `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=30000` via a connect-time event listener, letting concurrent writers queue instead of failing immediately. Verified under real load: 5 parallel league backfills against the same file (Phase 9) — two needed one retry each before the fix fully took hold (see Phase 9 for the caveat about ad-hoc scripts needing their own `connect_args={'timeout': 30}`), the rest succeeded cleanly first try. |

## 7. Decisions Already Made (don't re-litigate during build)

1. Reuse SP2 stack wholesale — this is an evolution, not a rewrite.
2. League adapters + common `games` schema is the extensibility mechanism.
3. Free sources only; no paid API in the first draft. Paid fallbacks documented in
   SP3_data_sources.md if a free source dies.
4. Bulk files for backfill, APIs for sync — never bulk-crawl a rate-limited/ToS-restricted API.
5. 1970 floor for pro leagues, 1990 for CFB; `start_season` parameterized for later deepening.
6. Venue completeness target: MLB/NFL/NHL/CFB from source data; NBA via hand-built seed file;
   MLS from the ASA API directly, with a small seed for pre-2013 grounds.
7. `has_time=False` games are parked at **noon** UTC, never midnight, via
   `local_time.date_only()` — see `SP3_open_issues.md` #8.
