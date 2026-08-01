# SP3 Frontend Redesign — "Press Box" Hybrid

Full rebuild of the frontend around the **Press Box** concept (search-first stat terminal),
with the **Atlas** map folded in as a view and **Passport** stamp/keepsake elements as
flourishes. Replaces the current filter-dropdown + card-list UI.

Concept mockups (Claude artifacts, built from the real 160-game attendance log):

- Concept 1 · The Passport — https://claude.ai/code/artifact/8b81202f-5eb6-455b-8ed3-842d54038eee
- Concept 2 · Press Box (chassis) — https://claude.ai/code/artifact/caac7918-fd41-4d24-8991-39a1d5bb5e18
- Concept 3 · The Atlas (map view) — https://claude.ai/code/artifact/3fc73045-fbe5-4b52-9398-c8be17cca444

## Design decisions (locked)

- **Information architecture**: top-level views = **Find** (omnibox + team workspace),
  **Map** (Atlas), **My Games** (attendance log with stamp marks), **Stats** (passport
  identity page + tile-grid states map), **Admin** (unchanged).
- **Search-first**: a single omnibox finds teams across all leagues (grouped results,
  league filter tabs, per-team attended counts). Selecting a team opens the workspace:
  game log + record-when-attended tiles + games-by-season chart + most-visited venues.
- **League color code** (fixed slots, colorblind-validated palette; same order everywhere):
  CFB `#2a78d6` blue · MLB `#008300` green · NFL `#e87ba4` magenta · NBA `#eda100` yellow ·
  NHL `#1baf7a` aqua · CBB `#eb6834` orange (dark-mode variants in the mockups' CSS tokens).
- **Themes**: light + dark via CSS custom-property tokens (`prefers-color-scheme` +
  `data-theme` override), dark-first styling like the Press Box mockup.
- **Logos**: real team logos everywhere a team appears; colored monogram badge
  (league color + abbreviation) as the fallback for teams without one.
- **Passport flourishes**: red "ATTENDED" stamp marks in game rows; unattended games at
  half-ink one tap from a stamp; Stats page becomes the passport identity page
  (totals, record-when-attended, MRZ-style footer line, tile-grid US map of states).
- **Map**: inline TopoJSON US map rendered client-side (no tile server, works offline,
  matches Docker single-container deploy). Venue dots sized by games attended, colored
  by league, click → venue panel with that venue's games.

## Phase 1 — Team logos (backend) ✦ prerequisite for everything

ESPN's hidden API (already an accepted source in `docs/SP3_data_sources.md`) provides
team lists with logo URLs for all six leagues. One-time scrape, stored locally — no
hotlinking at runtime.

- [x] `teams.logo_url` column (nullable String) + Alembic migration (`b4c9e1f7a2d3`)
- [x] Fix `alembic/env.py` to honor `DATABASE_URL` (was hardcoded to the ini URL,
      so the Docker `alembic upgrade head` would have migrated the wrong file)
- [x] Scrape script `backend/scripts/fetch_team_logos.py`:
      pulls ESPN team lists per league (`site.api.espn.com/.../teams`), matches to DB
      teams by normalized name (active teams only — historical/relocated identities keep
      the monogram fallback), downloads PNGs to `backend/data/logos/<league>/<team_id>.png`,
      sets `logo_url = /logos/<league>/<team_id>.png`. Idempotent; throttled.
- [x] Serve logos: FastAPI `StaticFiles` mount at `/logos` (from `data/logos`, which is
      the mounted `./data` volume in Docker — survives rebuilds, unlike `backend/static/`
      which Vite wipes on every build)
- [x] `logo_url` in `TeamResponse` schema
- [x] Exclude logos from version control (`backend/data/logos/` in `.gitignore`)
- [x] Run scrape locally (2026-07-15): **1,081 logos**, 62 MB. Verified `/logos/cfb/217.png`
      serves 200. Note: prod/staging must run the scrape once inside the container
      (or copy `backend/data/logos/` into the host `./data` volume).

Match results (2026-07-15 run):

| League | DB active teams | Matched | Notes |
|---|---|---|---|
| CFB | 1,911 | 597 | all FBS/FCS + some others; rest are historical schools |
| CBB | 1,386 | 362 | effectively all current D-I |
| MLB | 30 | 27 | misses are stale "active" rows (Indians, Quakers, Browns) |
| NFL | 32 | 32 | complete |
| NBA | 34 | 30 | all real NBA; misses are international exhibition teams |
| NHL | 62 | 33 | all 32 current + Utah alias; rest defunct identities |

## Phase 2 — Search & stats API

- [x] `GET /api/teams/search?q=` — cross-league team search: matches
      name/nickname/city, returns league_code, logo_url, and the current user's
      attended count per team; ranks attended > prefix match > active > name.
- [x] `GET /api/teams/{id}/attendance-stats` — record when attended (W–L–T from
      that team's perspective), games-by-season counts, most-visited venues,
      first/last game dates.
- [x] Game list responses carry logo_urls automatically (GameListResponse nests
      TeamResponse, which gained logo_url in Phase 1).
- [x] `GET /api/attendance/stats` additions (non-breaking): `games_by_state`,
      `venues` (name/city/state/count, sorted), `first_game_date`, `last_game_date`.
      (Per-league season matrix deferred until a view needs it.)

## Phase 3 — Press Box chassis (frontend rebuild)

- [x] Token-based theme system (light/dark via CSS vars + `data-theme` toggle,
      Tailwind v4 `@theme inline` semantic utilities) + league color constants
- [x] App shell: top bar (wordmark, nav: Find / My log / Stats / Admin, theme toggle)
- [x] Omnibox + grouped typeahead (league tabs pre-filter; arrow/enter/escape keys)
- [x] Team workspace (`/teams/:id` rewrite): game log table (attended stamp,
      half-ink unattended rows, attended-only toggle, season select), record tiles,
      games-by-season SVG chart, top-venues bars
- [x] Attend/unattend inline in the log (stamp click removes; verified end-to-end)
- [x] TeamBadge component: logo image with colored-monogram fallback
- [x] Find home page: omnibox hero + "Your teams" shortcut chips
      (Games/Dashboard pages retired in Phase 6)

## Phase 4 — Atlas map view

- [x] `venues.latitude` / `venues.longitude` columns + migration (`c8e2f4a6b1d9`)
- [x] Geocode backfill script `backend/scripts/geocode_venues.py` — Nominatim
      city/state lookup at 1 req/s with a persistent cache; attended venues by
      default, `--all` for the full table. All 37 attended venues geocoded.
- [ ] Backfill missing venue rows on sync-imported games (e.g. the NBA Finals game
      has no venue) — map shows a "N games missing venue data" note meanwhile
- [x] `GET /api/attendance/venues` — per-venue attended counts + coords + league
      mix + count of attended games lacking a venue row
- [x] Map view (`/map`): inline SVG US map (shared lat/lon projection), dots sized
      by count / colored by league, hover tooltip, click → venue panel with that
      venue's games, league chips (empty leagues disabled), season timeline strip;
      overlapping same-city venues fan out a few px
- [x] **Done (2026-07-27):** map outline replaced with a real `d3-geo`
      `geoAlbersUsa` projection over `us-atlas` Census boundaries
      (`components/map/usOutline.ts`), instead of the original ~90-point
      hand-typed equirectangular polygon. Alaska/Hawaii deliberately excluded
      (dropped from the projected geometry, per user decision — no non-continental
      venues in this dataset) rather than rendered as insets, closing this out
      without needing the originally-planned inset layout.
- [x] **Done (2026-07-27):** the map only ever showed CFB/MLB/CBB venues because
      the NFL and NHL adapters never captured city/state (their sources don't
      supply it) and NBA's bulk source only carries venue data for its current
      season. Fixed via hand-built venue seeds — see Phase 7's `nba_arenas.csv`
      entry and `services/adapters/venue_seed.py`. NFL is keyed by nflverse's
      own (already-stable) `stadium_id`. NHL arenas are keyed by **team +
      season-range**, not by the API's display name: NHL naming-rights deals
      change every few years, and an earlier name-keyed version of this seed
      would have silently dropped a team's venue off the map the next time
      its arena got renamed. Keying by team+era means a rename just updates
      the existing row's `name` instead of orphaning a new, uncoordinated one.
      MLB/CBB were unaffected — they already captured city/state; only need
      `scripts/geocode_venues.py` re-run for venues attended since the
      2026-07-12 run.

## Phase 5 — Passport flourishes

- [x] Stats page → passport identity page: hero totals (games / venues / states /
      years), MRZ-style footer, tile-grid US states map (pure CSS grid, ink depth
      by games per state)
- [x] My Games → entry-stamp cards for the six most recent games + compact ledger
      rows with logos, inline notes editing, removal
- [x] Empty leagues shown as "awaiting first stamp" chips on the Stats page

## Phase 6 — Cleanup & ship

- [x] Remove dead pages/components (Games, Dashboard, GameCard, GameFilters;
      `/games` route dropped — Find + team workspace replace it)
- [x] Type-check + build clean; backend suite 154 passing; all views smoke-tested
      in the built app (search → workspace → attend/unattend, map dots + panel,
      stamps, stats, theme toggle)
- [ ] Mobile polish pass (tables scroll and the nav collapses, but the map and
      omnibox deserve a real narrow-viewport review on a phone)
- [ ] Docker build + deploy to staging (docker31), then production — remember to
      run `scripts/fetch_team_logos.py` and `scripts/geocode_venues.py` against
      the production DB (or copy `backend/data/logos/` into the `./data` volume)
- [x] CLAUDE.md points at this plan; Login/Register kept their own light styling
      (self-contained pages; token pass optional later)
- [x] Resilience: a top-level `ErrorBoundary` wraps every route, so a render
      error shows a recoverable "Something went wrong" page with a reload
      action instead of unmounting the tree to a blank screen. The error text
      goes to `console.error` with the component stack, never into the DOM —
      it can carry internal paths or response fragments. Paired with request
      timeouts in `api/client.ts` (30s default, 10m for admin imports/syncs)
      so a stalled backend surfaces as an error rather than a forever-spinner.

## Compliance

- ESPN hidden API: unofficial — one-time/occasional scrapes only, throttled, with a
  descriptive User-Agent; logos cached locally so the app never hotlinks ESPN.
- Existing rules unchanged: MLB Stats API sync-only; never scrape Sports-Reference.
  NBA sync also runs on ESPN as of 2026-08-01 (nba.com is Akamai-blocked from our
  hosts), under the same throttled/descriptive-User-Agent terms as the logo scrape.
