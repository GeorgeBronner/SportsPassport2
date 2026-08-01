# SP3 Data Sources Research

Research into game-level data sources (teams, location, date, score) for MLB, NFL, NBA, and NHL,
covering at least 1990 back to 1970 where possible. Modeled on the SportsPassport2 approach:
**one big historical load, then lightweight incremental updates.** Hobby project — zero ongoing
cost strongly preferred.

Research date: July 2026.

---

## TL;DR — Recommended Picks

| League | Historical Load (one-time) | Ongoing Updates (free) | Paid Fallback |
|--------|---------------------------|------------------------|---------------|
| MLB    | Retrosheet game logs (free, 1871–present) | MLB Stats API (`statsapi.mlb.com`) | SportsDataIO |
| NFL    | Kaggle "NFL scores and betting data" CSV (free, 1966–present) | nflverse `games.csv` (auto-updated) | SportsDataIO or MySportsFeeds |
| NBA    | `nba_api` LeagueGameFinder off `stats.nba.com` (free, 1946–present) or Kaggle bulk CSV | `nba_api` / `stats.nba.com` | BALLDONTLIE GOAT ($39.99/mo) or SportsDataIO |
| NHL    | Official NHL API (`api-web.nhle.com`, free, 1917–present) | Same official NHL API | SportsDataIO |

**Bottom line: every league can be covered back to 1970 (and well before) entirely for free.**
A paid source is genuinely optional here — the free options for all four leagues are either
official (MLB, NHL), community-maintained and battle-tested (nflverse, Retrosheet), or stable
unofficial endpoints with mature client libraries (`nba_api`, ESPN).

---

## Architecture Notes (SP2 Model Applied to SP3)

SportsPassport2 does a bulk historical import from CollegeFootballData.com plus an admin
"refresh" endpoint. For SP3 the equivalent is:

1. **Initial load**: download bulk files (CSV/JSON) per league, normalize into a common
   `games` schema (`league`, `season`, `date`, `home_team`, `away_team`, `home_score`,
   `away_score`, `venue`, `city/state`), import once.
2. **Ongoing sync**: a scheduled job (daily or weekly) hits each league's free API for
   recent dates only — tiny request volume, well within every free tier.
3. **Venue mapping**: several historical sources give a park/venue ID or name; keep it.
   It's exactly what a "stadiums visited" stat needs, and it's the hardest thing to
   backfill later. Retrosheet and NHL/MLB official APIs include it; for NFL the Kaggle
   dataset includes stadium + weather; NBA venue data is weakest historically (home team's
   arena can be inferred from a separate arenas-by-season table you build once).
4. **Extensibility**: keep `league` as a first-class column and per-league adapter modules
   for import/sync. Adding MLS later = one new adapter (ESPN and TheSportsDB both already
   carry MLS).

Extra fields worth preserving beyond the minimum: venue/park ID, attendance, game type
(regular/playoff), season, day/night, neutral-site flag, overtime/shootout flag (NHL),
innings (MLB extra innings).

---

## MLB

### Suggested Free (Historical): Retrosheet Game Logs
[Retrosheet](https://www.retrosheet.org/) is the gold standard for historical baseball data.
The [game logs](https://www.retrosheet.org/gamelogs/index.html) cover **every MLB game from
1871 to present** with date, teams, score, ballpark, attendance, day/night, and much more —
downloadable as flat files, with newer [CSV downloads](https://www.retrosheet.org/downloads/csvdownloads.html)
including a `gameinfo.csv` with game-level info. License is unusually generous: recipients are
free to make any use of the data, including commercial. One ZIP download covers your entire
1970+ requirement.

### Suggested Free (Ongoing): MLB Stats API
The official [MLB Stats API](https://statsapi.mlb.com/) (`statsapi.mlb.com/api/v1/`) is
publicly accessible with **no API key**. Schedule/score endpoints support historical seasons
too. Terms: free for individual, non-commercial, non-bulk use — fine for a daily "fetch
yesterday's scores" job on a hobby app, but don't use it for the bulk backfill (that's what
Retrosheet is for). The [MLB-StatsAPI Python wrapper](https://pypi.org/project/MLB-StatsAPI/)
is mature.

### Suggested Paid: SportsDataIO
[SportsDataIO MLB API](https://sportsdata.io/mlb-api) — decades of historical data, clean
REST API, free trial (scrambled data). Pricing is "contact sales" tier, typically $custom/mo.

### All MLB sources found

| # | Source | Coverage | Cost | Notes |
|---|--------|----------|------|-------|
| 1 | [Retrosheet game logs](https://www.retrosheet.org/gamelogs/index.html) | 1871–present | Free | Best-in-class historical bulk; permissive license |
| 2 | [MLB Stats API](https://statsapi.mlb.com/) | ~1901–present | Free (non-commercial, non-bulk) | Official; no key required; ideal for incremental updates |
| 3 | [Retrosheet Kaggle mirror](https://www.kaggle.com/datasets/mexwell/retrosheet-baseball-logs) | 1871–recent | Free | Convenience mirror of #1 |
| 4 | [SportsDataIO MLB](https://sportsdata.io/mlb-api) | Decades of history | Paid (free scrambled trial) | Commercial-grade |
| 5 | [The Baseball Cube](https://www.thebaseballcube.com/content/box_main/) | 1957–present boxscores | Free to browse / paid data store | Built on Retrosheet; site, not API |
| 6 | [BALLDONTLIE MLB](https://www.balldontlie.io/) | Multi-decade | Freemium (5 req/min free) | Scores in higher tiers; see multi-sport section |
| 7 | [MySportsFeeds](https://www.mysportsfeeds.com/data-feeds/) | Recent seasons | Free for non-commercial hobby use | Historical depth limited vs Retrosheet |
| 8 | [ESPN hidden API](https://github.com/pseudo-r/Public-ESPN-API) | Recent decades | Free (unofficial) | Good backup update source |
| 9 | [Apify MLB Stats API scraper](https://apify.com/gentle_cloud/mlb-stats-api) | Same as #2 | Freemium | Wrapper around #2; unnecessary if calling directly |
| 10 | [RapidAPI baseball collection](https://rapidapi.com/collection/baseball-api) | Varies | Freemium | Various small APIs; nothing beats #1+#2 combo |

---

## NFL

### Suggested Free (Historical): Kaggle "NFL scores and betting data" (Spreadspoke)
The [Kaggle NFL scores and betting data dataset](https://www.kaggle.com/datasets/tobycrabtree/nfl-scores-and-betting-data)
(`spreadspoke_scores.csv`) covers **every NFL game since 1966** — date, teams, scores, stadium,
weather, playoff flags. One free CSV download that fully covers 1970+. Also available directly
from [Spreadspoke](https://spreadspoke.com/data.html). Sourced from ESPN/NFL.com/Pro Football
Reference.

**Access status (re-checked 2026-08-01): freely downloadable, no login.** A 2026-07-11 check
concluded this file had moved behind a Kaggle account or a paid tier, which is why the NFL
adapter shipped with a 1999 floor. That is no longer the case — the public download API
serves it anonymously:

```bash
curl -L -o nfl.zip https://www.kaggle.com/api/v1/datasets/download/tobycrabtree/nfl-scores-and-betting-data
```

Note that **only `GET` works** — a `HEAD` probe against that URL returns 404, which is an easy
way to wrongly conclude the dataset is gone. This is the same access pattern the MLS Kaggle
file uses. It now backs NFL 1970–1998 (SP3_plan.md Phase 11); nflverse still owns 1999+.

**Quality, measured rather than assumed** (see Phase 11 for the full write-up): on the
1999–2024 overlap it agrees with nflverse exactly — 6,991 games each, zero per-season
variance. Its 1970–1998 slice has no null date/score/stadium and no duplicate natural key.
Caveats: **no kickoff times at all** (the era imports date-only), no attendance, no overtime
column, and its `stadium` field names the *building* rather than the name it carried at the
time. One genuine defect — Cardinals home games 1994–98 are attributed to a stadium that
opened in 2006 — is corrected on import.

### Suggested Free (Ongoing): nflverse
[nflverse](https://github.com/nflverse) is the community-maintained NFL data ecosystem. The
[`games.csv`](https://github.com/nflverse/nfldata/blob/master/data/games.csv) file (Lee Sharpe's
schedule/results data, 1999–present) is **auto-updated in-season and fetchable by raw URL** —
no API key, no rate limits, just an HTTP GET of a CSV. Perfect cron-job update source.
[nflreadr docs](https://nflreadr.nflverse.com/reference/load_schedules.html) describe the schema.
You could even use nflverse for the historical load and Kaggle only for 1970–1998.

### Suggested Paid: SportsDataIO or MySportsFeeds
[SportsDataIO NFL API](https://sportsdata.io/nfl-api) for commercial-grade data, or
[MySportsFeeds](https://www.mysportsfeeds.com/data-feeds/) which is cheap/free for
non-commercial hobbyist use.

### All NFL sources found

| # | Source | Coverage | Cost | Notes |
|---|--------|----------|------|-------|
| 1 | [Kaggle NFL scores (Spreadspoke)](https://www.kaggle.com/datasets/tobycrabtree/nfl-scores-and-betting-data) | 1966–present | Free (no login — `GET` only, `HEAD` 404s) | **In use for 1970–1998.** One CSV, includes stadium + weather; ideal bulk load |
| 2 | [nflverse `games.csv`](https://github.com/nflverse/nfldata/blob/master/data/games.csv) | 1999–present | Free | **In use for 1999+ and all sync.** Auto-updated; raw-URL fetch |
| 3 | [Spreadspoke direct download](https://spreadspoke.com/data.html) | 1966–2025 | Free | Same data as #1 without a Kaggle account |
| 4 | [ESPN hidden API](https://gist.github.com/nntrn/ee26cb2a0716de0947a0a4e9a157bc1c) | Recent decades | Free (unofficial) | `scoreboard?dates=YYYY` endpoints; good backup |
| 5 | [Big Balls Data](https://bigballsdata.com/nfl-api) | nflverse-backed | Free tier (1,000 req/day) | REST wrapper over nflverse if you prefer an API to CSVs |
| 6 | [MySportsFeeds](https://www.mysportsfeeds.com/data-feeds/) | Recent seasons | Free non-commercial / paid | Schedules, scores, boxscores |
| 7 | [SportsDataIO NFL](https://sportsdata.io/nfl-api) | Deep history | Paid | Commercial-grade |
| 8 | [Pro-Football-Reference](https://www.pro-football-reference.com/) | 1920–present | Free to browse; **no bulk/scrape** | See Sports-Reference warning below |
| 9 | [BALLDONTLIE NFL](https://www.balldontlie.io/) | Multi-decade | Freemium | See multi-sport section |
| 10 | [RapidAPI NFL APIs](https://rapidapi.com/search/nfl) | Varies | Freemium | Assorted; nothing beats #1+#2 |

---

## NBA

### Suggested Free (Historical + Ongoing): stats.nba.com via `nba_api`
The [`nba_api` Python package](https://github.com/swar/nba_api) wraps NBA.com's official-but-
undocumented `stats.nba.com` endpoints. The
[LeagueGameFinder endpoint](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/leaguegamefinder.md)
returns **every NBA game since 1946** (60,000+ games) with date, matchup, and score. One
source covers both the bulk backfill (paginate season by season, being polite with rate
limiting — stats.nba.com throttles aggressive clients) and the daily update job. No key needed.

If you'd rather not script the backfill, the
[Kaggle NBA dataset (1947–present, updated daily)](https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores)
has a ready-made `Games.csv` — grab it once and switch to `nba_api` for updates.

**Caveat:** NBA venue data is thin historically. Plan to build a small
"arena-by-team-by-season" lookup table (a one-time manual/Wikipedia effort) rather than
expecting it from the API.

### Suggested Paid: BALLDONTLIE GOAT or SportsDataIO
[BALLDONTLIE](https://www.balldontlie.io/) has NBA data back to 1946 with a clean modern API;
scores/boxscores need the GOAT plan (~$39.99/mo per [SportsAPI.com's review](https://sportsapi.com/api-directory/balldontlie/)).
[SportsDataIO NBA](https://sportsdata.io/nba-api) is the commercial-grade alternative.

### All NBA sources found

| # | Source | Coverage | Cost | Notes |
|---|--------|----------|------|-------|
| 1 | [`nba_api` / stats.nba.com](https://github.com/swar/nba_api) | 1946–present | Free | Best free option; covers backfill and updates |
| 2 | [Kaggle NBA dataset (eoinamoore)](https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores) | 1947–present, updated daily | Free | Ready-made `Games.csv` bulk load |
| 3 | [BALLDONTLIE](https://www.balldontlie.io/) | 1946–present | Freemium (5 req/min free; scores on paid tiers) | Nice API; free tier too limited for backfill |
| 4 | [ESPN hidden API](https://github.com/pseudo-r/Public-ESPN-API) | Recent decades | Free (unofficial) | Backup update source |
| 5 | [SportsDataIO NBA](https://sportsdata.io/nba-api) | Deep history | Paid | Commercial-grade |
| 6 | [API-Sports API-NBA](https://api-sports.io/) | ~2008–present | Freemium (100 req/day free) | History too shallow for SP3 backfill |
| 7 | [BigDataBall NBA](https://www.bigdataball.com/datasets/nba-data/) | Recent seasons | Paid (per-season Excel) | Betting/DFS oriented; overkill here |
| 8 | [MySportsFeeds](https://www.mysportsfeeds.com/data-feeds/) | Recent seasons | Free non-commercial / paid | Limited history |
| 9 | [Basketball-Reference](https://www.basketball-reference.com/) | 1946–present | Free to browse; **no bulk/scrape** | See Sports-Reference warning below |
| 10 | [RapidAPI API-NBA](https://rapidapi.com/api-sports/api/api-nba) | ~2008–present | Freemium | Same as #6 via RapidAPI |

---

## NHL

### Suggested Free (Historical + Ongoing): Official NHL API
The official [NHL API](https://api-web.nhle.com/v1/) is free, keyless, and its schedule/score
data goes back to **1918** — the single cleanest situation of all four leagues: one official
free source for both backfill and updates. Community docs and wrappers:
[nhl-api-py on PyPI](https://pypi.org/project/nhl-api-py/), plus endpoint walk-throughs like
[this Medium guide](https://medium.com/@vtashlikovich/nhl-api-what-data-is-exposed-and-how-to-analyse-it-with-python-745fcd6838c2).
Includes venue, game type, and OT/SO outcomes.

If you prefer a one-shot bulk file instead of scripting the backfill, the
[Kaggle NHL Games Database (1917–2025)](https://www.kaggle.com/datasets/flynn28/nhl-games-database)
has every game with scores in CSV.

### Suggested Paid: SportsDataIO
[SportsDataIO NHL API](https://sportsdata.io/nhl-api) — but honestly unnecessary given the
official free API.

### All NHL sources found

| # | Source | Coverage | Cost | Notes |
|---|--------|----------|------|-------|
| 1 | [Official NHL API](https://api-web.nhle.com/v1/) | 1918–present | Free | Best option, period; official, keyless, full history |
| 2 | [Kaggle NHL Games Database](https://www.kaggle.com/datasets/flynn28/nhl-games-database) | 1917–2025 | Free | Ready-made CSV bulk load |
| 3 | [nhl-api-py](https://pypi.org/project/nhl-api-py/) | Same as #1 | Free | Python wrapper for #1 |
| 4 | [MoneyPuck data downloads](https://moneypuck.com/data.htm) | 2007–present | Free | Analytics-oriented; too shallow for backfill |
| 5 | [Kaggle NHL Game Data (martinellis)](https://www.kaggle.com/datasets/martinellis/nhl-game-data) | 2000s–~2020 | Free | Older, partially stale |
| 6 | [SportsDataIO NHL](https://sportsdata.io/nhl-api) | Deep history | Paid | Commercial-grade |
| 7 | [Kaggle Professional Hockey Database](https://www.kaggle.com/datasets/open-source-sports/professional-hockey-database) | Historical | Free | Season-level stats, not game scores |
| 8 | [ESPN hidden API](https://github.com/pseudo-r/Public-ESPN-API) | Recent decades | Free (unofficial) | Backup update source |
| 9 | [Hockey-Reference](https://www.hockey-reference.com/) | 1917–present | Free to browse; **no bulk/scrape** | See Sports-Reference warning below |
| 10 | [BALLDONTLIE NHL](https://www.balldontlie.io/) | Multi-decade | Freemium | See multi-sport section |

---

## College Basketball (CBB)

Research into game-level data sources (teams, home/away, date, score, venue) for NCAA Division I
men's basketball, evaluated against the same hobby/zero-cost bar as MLB/NFL/NBA/NHL above.
Research date: July 2026. **Update:** the original pass here (docs-only, no live API access)
concluded the cleanest structured API (CollegeBasketballData.com) only reached back to 2003 —
live testing during the actual adapter build found real data back to at least 1950. See the
"Correction" callout further down for details; the app ships with a 1990 floor regardless, as a
scope choice.

### TL;DR — Recommended Pick

| League | Historical Load (one-time) | Ongoing Updates (free) | Paid Fallback |
|--------|---------------------------|------------------------|---------------|
| CBB    | CollegeBasketballData.com (CBBD), free API key, 1950s–present (see correction below) | Same: CBBD `/games` | SportsDataIO NCAA Basketball |

**Correction (2026-07-12, adapter build session):** the "2003 floor" below was wrong — it was
inferred from marketing/blog pages without a live API call. Live testing while building
`CbbAdapter` found real, clean game data (real teams, real scores) at `season=1950` (1,240
games) and every decade sampled between 1950 and 2024. **The app's CBB adapter ships with a 1990
floor anyway** — a scope decision matching CFB's floor, not a data-availability limit; see
`SP3_plan.md` Phase 8. The paragraph immediately below (recommending 2003) is the original,
inaccurate research and is kept for context on how the recommendation changed, not as current
guidance.

**Also found during the adapter build: `GET /games` caps at exactly 3,000 rows**, regardless of
`season`/`seasonType` filters (three different season queries each returned exactly 3,000 rows,
with a 2023-24 regular-season query cutting off in mid-January despite the season running to
April). The real pagination mechanism is `startDateRange`/`endDateRange` (verified working;
monthly chunks stay safely under the cap even in the highest-volume month and the tournament
month). Anyone building against this API should chunk by date range, not rely on `season` alone.

**Original (inaccurate) floor-year recommendation, superseded above:** 2003. This was a hard
downgrade from the app's CFB/pro-league 1990 floor, reasoned to be where the one clean,
structured, adapter-friendly source starts. Deeper history (back to 1996) exists but only via a
dataset with commercial-use-restricted licensing (see Kaggle NCAA Basketball entry below) — not
worth building the pipeline on for a few extra seasons of top-line scores, was the (mistaken)
thinking. In fact CBBD itself has much deeper history than 2003; only the restricted Kaggle
dataset's *box-score/play-by-play* depth is actually capped around 1996 — final scores go back
much further within CBBD itself.

**Why CBBD is the natural fit:** it's built and maintained by the same team as
CollegeFootballData.com — the "About" page and shared Patreon
([patreon.com/collegefootballdata](https://www.patreon.com/collegefootballdata)) confirm
CBBD is CFBD's sister project (maintainer: Bill Radjewski). Same auth model (register for a free
API key, send as a `Bearer` token — identical to `CfbAdapter`'s `Authorization` header pattern),
same free-tier shape (1,000 calls/month, matching CFBD's documented free tier at
[collegefootballdata.com/api-tiers](https://collegefootballdata.com/api-tiers)), and official
Python (`cbbd` on [PyPI](https://pypi.org/project/cbbd/), generated from an OpenAPI spec) and R
(`cbbd-r`) clients mirroring CFBD's tooling. A `CbbAdapter` could very plausibly be a near-copy of
`cfb.py` — swap the base URL and field names. Confirmed men's D-I coverage 2003–present, games from
2003+, betting lines from 2013+ (per Patreon/blog and third-party wrapper docs — see sources). It
currently does **not** offer NCAA women's data, which is fine since scope here is men's D-I.

**Live-verified 2026-07-12:** the existing `CFB_API_KEY` (from CFBD) works unmodified as a CBBD
Bearer token — confirmed with real `GET /teams` (1,518 rows) and `GET /games?season=2024` (full
season, ~2.4MB) calls against `api.collegebasketballdata.com`. No separate CBBD signup needed.
This also resolves both open items flagged below:
- **Venue**: `/games` rows carry `venueId`/`venue`/`city`/`state` directly (plus `attendance`) —
  no separate arena lookup table needed, unlike NBA.
- **Non-D-I opponents**: better than expected. A real buy-game in the sample (IU Indianapolis vs.
  Spalding, an NAIA school) showed the non-D-I opponent *does* get a full team row in `/teams`
  (id, `sourceId`, `school`, `mascot`, `abbreviation`) — just with `currentVenue`/`currentCity`/
  `currentState`/`conference` all null, since CBBD doesn't track those for non-D-I programs.
  `/teams` returned 1,518 rows total, far more than the ~365 D-I teams, confirming it's "any team
  that's played a tracked game," not a D-I-only registry. So the no-full-non-D-I-data assumption
  behind the classification design question below still holds (no conference/venue for those
  teams), but the manual seed-lookup fallback for opponent identity is unnecessary — a plain
  `/teams` fetch already covers it, same as CFBD's FBS/FCS handling.

### Suggested Free (Historical): CollegeBasketballData.com (CBBD)
[CollegeBasketballData.com](https://collegebasketballdata.com/) — see rationale above. Coverage:
men's D-I games 2003–present. Free API key at
[collegebasketballdata.com/key](https://collegebasketballdata.com/key); rate limits and full ToS
weren't fully documented on the public pages I could reach without an account — same due-diligence
gap existed for CFBD until a key was actually requested, so treat this the same way: register,
read the Terms & Conditions page linked in the footer, and confirm limits before scripting a full
2003–present backfill.

### Suggested Free (Ongoing): CollegeBasketballData.com (CBBD)
Same API, same key — call `/games` (or `/scoreboard` for live/day-of data) filtered to recent
dates, exactly like the CFB adapter's `sync_recent`. One less integration to maintain than picking
a separate ongoing source.

**Backup/secondary ongoing source:** ESPN's hidden API has a standard college-hoops scoreboard
endpoint: `https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates=YYYYMMDD&groups=50&limit=500`
(`groups=50` + a high `limit` is needed to get the full Division I slate for a date, not just
ranked/featured games). No key, no auth, same "unofficial and could change" caveat as ESPN's other
sport endpoints already noted in this doc. Good as a redundant/fallback update source, not a
primary.

### Suggested Paid: SportsDataIO
[SportsDataIO NCAA Basketball API](https://sportsdata.io/ncaa-college-basketball-api) — same
posture as the other four leagues' paid fallback: commercial-grade, deep history, "contact sales"
pricing, free scrambled trial. Unnecessary unless CBBD's free tier proves too thin or the app ever
goes commercial. [Sportradar NCAAMB API](https://developer.sportradar.com/basketball/docs/ncaamb-ig-api-basics)
is the enterprise-grade alternative (2013+ coverage per their docs), well over hobby budget.

### All CBB sources found

| # | Source | Coverage | Cost | Notes |
|---|--------|----------|------|-------|
| 1 | [CollegeBasketballData.com (CBBD)](https://collegebasketballdata.com/) | 2003–present (betting lines 2013+) | Free (1,000 calls/mo tier; more via Patreon) | Sister project to CFBD, same maintainer/auth model; best fit given existing CFB adapter pattern |
| 2 | [Kaggle "NCAA Basketball" (Google BigQuery public dataset)](https://www.kaggle.com/datasets/ncaa/ncaa-basketball) | Final scores 1996–present; box scores/play-by-play 2009–present | Free to access | **Compliance flag**: data is Sportradar-sourced with a copyright notice restricting use to "internal research and testing purposes... not to be used for any business or commercial purpose." Stricter than MLB Stats API's non-commercial carve-out. Do not build the pipeline on this. |
| 3 | [Kaggle "College Basketball Dataset" (andrewsundberg)](https://www.kaggle.com/datasets/andrewsundberg/college-basketball-dataset) | 2013–present (seasons 2013–2019, 2021–2025+) | Free | Advanced efficiency metrics (KenPom-style), not raw game logs; wrong shape for a `games` table, skip |
| 4 | [ESPN hidden API](https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard) | Recent decades (undocumented how far back `dates=` reliably goes; treat as ~2002+ at best) | Free (unofficial) | Good ongoing/backup source; not for bulk backfill given undocumented historical reliability |
| 5 | [NCAA.com via henrygd/ncaa-api](https://github.com/henrygd/ncaa-api) | Current/recent only | Free, MIT-licensed wrapper | Scrapes ncaa.com directly; no explicit ToS clearance from NCAA for this wrapper; public hosted instance capped at 5 req/sec; self-host if used at all; no bulk historical endpoint (only current stats/scoreboard pages) — avoid as a pipeline source, same spirit as the Sports-Reference warning even though it's not a Sports-Reference property |
| 6 | [TheSportsDB — "NCAA Division I Basketball Mens" (league 4607)](https://www.thesportsdb.com/league/4607-ncaa-division-i-basketball-mens) | Fixtures/results present but historically thin, consistent with this doc's existing NBA/NHL notes on TheSportsDB | Free / ~$9 Patreon premium | Fine for team metadata/logos/an auxiliary update feed; not a historical backbone |
| 7 | [BALLDONTLIE NCAAB](https://ncaab.balldontlie.io/) | Includes AP/Coaches poll rankings, standings, games; historical depth undocumented publicly | Freemium (5 req/min free tier includes games; box scores/PBP/standings need $9.99–$39.99/mo GOAT tier, per-sport) | Free tier likely fine for a "recent scores" ongoing check, but depth for backfill is unclear and priced per sport on top of any NBA/NFL/MLB BALLDONTLIE usage already in place |
| 8 | [SportsDataIO NCAA Basketball](https://sportsdata.io/ncaa-college-basketball-api) | Deep history | Paid, contact sales (free scrambled trial) | Commercial-grade; the "suggested paid" pick |
| 9 | [Sportradar NCAAMB API](https://developer.sportradar.com/basketball/docs/ncaamb-ig-api-basics) | 2013–present | Paid, enterprise | Same underlying data as the restricted Kaggle set (#2); over-budget/overkill for a hobby app |
| 10 | Sports-Reference (sports-reference.com/cbb, basketball-reference.com college pages) | 1894–present (win/loss); modern era for full box scores | Free to browse; **no bulk/scrape** | **Off limits** — same Sports-Reference family policy already documented below: no tools built on scraped data, aggressive rate-limit/blocking, $5,000+ custom exports. Do not use for CBB either, including via basketball-reference.com's college arm. |

### Scale sanity check

- **Teams**: NCAA Division I men's basketball has **~365 teams** (361 full D-I conference members
  plus a handful in transition from D-II, 2025–26 figures) — roughly **2.5–3x** the CFB adapter's
  FBS team count (~134), and far more than any pro league in this doc (NFL 32, NBA/NHL 30-32,
  MLB 30).
- **Games**: D-I teams play **~30–38 games/season** each; total D-I games league-wide run
  **~5,800–6,000/season** (5,826 in 2018–19, a representative recent year — each game counted
  once).
- **Historical volume at the recommended 2003 floor**: roughly 23 seasons (2003–04 through
  2025–26) × ~5,800 games ≈ **~130,000–135,000 games**. If a future push to the 1996 floor (using
  a better-licensed source than the restricted Kaggle set, should one appear) ever happens, that
  adds ~7 more seasons ≈ another 40,000 games, for ~175,000 total.
- **Comparison to existing app scale**: the app already handles ~320k rows across 5 leagues. CBB
  at the 2003 floor adds roughly **40% more game rows** on top of that — a meaningful but not
  architecturally significant lift; SQLite handles this without issue (single-digit-million-row
  tables are routine for SQLite; this is two orders of magnitude below that). The team count
  (~365 new rows) and the volume of team↔season↔conference realignment bookkeeping (D-I conference
  membership churns yearly, more than CFB's FBS/FCS split) is the bigger practical complexity, not
  raw row count — worth budgeting import-logic time for conference-affiliation-by-season handling,
  similar to how the CFB adapter already carries `conference`/`division` per team.

### Non-Division-I opponents ("buy games" / exhibitions)

The app only needs to *log/track* D-I men's games (D-I is the CBB floor, same idea as CFB's
FBS-only floor), but D-I teams routinely schedule "buy games" against D-II, D-III, and NAIA
opponents, and a user could plausibly have attended one of those. The app doesn't need full
non-D-I rosters/standings/historical bulk data — just enough identity (name, ideally location) to
represent the opponent as a team row on a D-I team's game.

**Live-verified 2026-07-12** (see confirmation above) — this turned out better than the docs-only
research below assumed. A real `/games?season=2024` row shows a buy-game between IU Indianapolis
(D-I, Horizon League) and Spalding (NAIA): `homeTeamId`/`awayTeamId` are both populated numeric
IDs (camelCase in the raw JSON, not the snake_case the Python client docs implied), and Spalding
has a full row in `/teams` — `id`, `sourceId`, `school`, `mascot`, `abbreviation` — just with
`currentVenue`/`currentCity`/`currentState`/`conference` all `null`. So **no manual seed lookup is
needed**: a plain `/teams` fetch already gives every opponent a usable team identity, D-I or not,
the same way CFBD's `/teams` returns all-time rosters regardless of classification. What's genuinely
missing for non-D-I teams is location and conference, not identity — city/state has to stay null
for those rows, which is fine (matches this doc's general "nullable venue" pattern elsewhere).

**Design question for implementation (not resolved here):** CBB teams will need a `classification`
value on the `Team` row, following the existing precedent (`Team.classification`, and
`_counts_for_stats` in `backend/sports_passport/routers/attendance.py`, which currently treats
`classification is None or classification == "fbs"` as stats-eligible for CFB). Whoever builds the
`CbbAdapter` needs to decide: (a) what classification value(s) non-D-I opponents get (a single
generic non-D-I bucket is probably sufficient given the "no full non-D-I data" scope), and (b)
whether attendance stats should count only D-I-vs-D-I games, or any game involving at least one D-I
team (the latter seems more consistent with the existing FBS/FCS precedent, where FCS opponents
don't block a game from being logged — they just don't personally count as an "FBS team" in
team-based stats). This mirrors the FBS/FCS handling already in place and shouldn't need new
architecture, just a CBB-appropriate classification value and the same style of stats filter.

### Compliance/ToS notes specific to CBB

- **CBBD**: same posture as CFBD — free key, monthly call cap, Patreon tiers unlock more. No
  scraping involved (this is a documented, versioned, key-gated API), so it doesn't carry the
  Sports-Reference-style prohibition. Re-verify the Terms & Conditions page after requesting a key
  (not fully readable from the public marketing pages alone).
- **Kaggle "NCAA Basketball" BigQuery dataset**: flagged above — Sportradar's copyright notice
  restricts use to internal research/testing, explicitly excluding "business or commercial
  purpose." SportsPassport2 is non-commercial/personal-family use, which arguably clears the
  commercial-purpose bar, but "internal research and testing" is narrower language than "personal
  use" and doesn't obviously cover "runs as a self-hosted web app my family uses to log games
  attended." Given CBBD already covers 2003+ cleanly, there's no need to lean on this dataset —
  recommend leaving it out of the pipeline entirely rather than relying on a favorable reading of
  ambiguous terms.
- **ESPN hidden API**: same caveat as everywhere else in this doc — unofficial, undocumented,
  stable-but-not-guaranteed. Fine as a backup update layer only.
- **NCAA.com (via any wrapper)**: NCAA.com itself doesn't publish an official public API or clear
  data-reuse terms; the community wrappers scrape the site. Treat with the same caution as
  Sports-Reference even though there's no documented $5,000-export policy — no formal permission to
  build on top of it either. Skip it; CBBD + ESPN cover the need without this risk.
- **Sports-Reference (cbb arm)**: explicitly off limits, per the existing project-wide warning —
  no bulk use, no scraping, regardless of which Sports-Reference subdomain it's under.
- **BALLDONTLIE NCAAB**: standard BALLDONTLIE account/key terms (same family already covered for
  NBA/NFL/NHL/MLB in this doc); note it bills *per sport*, so adding CBB at a paid tier is an
  additive cost, not covered by an existing NBA subscription.

### Recommendation summary

Build `CbbAdapter` on **CollegeBasketballData.com** for both historical backfill and ongoing sync
— it's the only source here with clean licensing, a documented API, and an auth pattern that's
already proven out in `CfbAdapter`. **Built 2026-07-12** (`backend/sports_passport/services/
adapters/cbb.py`); see `SP3_plan.md` Phase 8 for the shipped floor year (1990, a scope choice,
not the 2003 data limit originally assumed here) and final verification numbers. Keep ESPN's
scoreboard endpoint in reserve as a backup ongoing-sync source, same role it plays for the other
four leagues, if CBBD's free tier ever proves too thin. Treat NCAA.com scrapers and the Kaggle
BigQuery dataset as sources to avoid outright rather than sources to lean on cautiously.

---

## Multi-Sport / Combined Sources

A single provider for all four leagues is appealing for code simplicity, but none of the free
multi-sport options match the per-league picks on historical depth. Best use: a **uniform
ongoing-update layer** (one adapter, four leagues) while historical loads stay per-league.

| Source | Leagues | Cost | Historical Depth | Verdict for SP3 |
|--------|---------|------|------------------|-----------------|
| [ESPN hidden API](https://github.com/pseudo-r/Public-ESPN-API) | All 4 + MLS + more | Free (unofficial, no key) | Varies; solid for recent decades via `?dates=` | Best free multi-sport update layer; unofficial = could break |
| [TheSportsDB](https://www.thesportsdb.com/free_sports_api) | All 4 + MLS + more | Free / $9-ish Patreon premium | Spotty for old seasons | Good for team/venue/logo metadata; weak on deep history |
| [BALLDONTLIE](https://www.balldontlie.io/) | All 4 + 20 leagues | Free tier 5 req/min; GOAT $39.99/mo; All-Access $299.99/mo | NBA to 1946; others multi-decade | Nicest paid multi-sport option for a hobby budget |
| [MySportsFeeds](https://www.mysportsfeeds.com/) | All 4 | Free for personal non-commercial (on request) | Limited older history | Worth requesting hobbyist access for the update layer |
| [SportsDataIO](https://sportsdata.io/) | All 4 + more | Paid, contact sales; free scrambled trial | Decades | The "suggested paid" across the board if SP3 ever goes commercial |
| [Sportradar](https://sportradar.com/media-tech/data-content/sports-data-api/) | All 4 + everything | Paid, enterprise | Deep | Enterprise-grade; overkill and over-budget for a hobby |
| [API-Sports](https://api-sports.io/) | All 4 | Free 100 req/day per sport; paid tiers | Only ~2008+ | History too shallow for SP3 |
| [Highlightly](https://highlightly.net/sport-api/) | All 4 + more | Free 100 req/day; paid tiers | Recent focus | Highlights/odds oriented; not a fit |

---

## Warnings & Constraints

- **Sports-Reference sites (pro-football-reference, basketball-reference, hockey-reference,
  baseball-reference)**: fantastic to browse, but their
  [data-use policy](https://www.sports-reference.com/data_use.html) prohibits building
  sites/tools on scraped data, they [rate-limit and block scrapers](https://www.sports-reference.com/bot-traffic.html)
  (20 req/min → day-long bans), and custom exports start at $5,000. **Do not build SP3's
  pipeline on these.** Listed above only for completeness/manual verification.
- **MLB Stats API terms**: free for individual, non-commercial, *non-bulk* use. Use Retrosheet
  for bulk; keep statsapi calls to incremental updates. If SP3 ever becomes commercial,
  revisit (MLBAM written authorization or a paid provider).
- **stats.nba.com**: undocumented and known to throttle/block aggressive clients. Backfill
  slowly (sleep between requests) or just use the Kaggle bulk CSV and avoid the issue.
- **ESPN hidden API**: unofficial and undocumented; endpoints have been stable for years but
  can change without notice. Fine as a backup/update layer, not as the only pillar.
- **Kaggle datasets**: community-maintained; verify row counts and recency at import time,
  and treat them as the *initial* load only — updates come from the league APIs.

## Future League Expansion (WNBA, CFL etc.)

- ESPN hidden API and TheSportsDB both already carry most leagues, so the
  ongoing-update adapter pattern extends naturally.
- The per-league adapter + common `games` schema is the design decision that makes
  this cheap. MLS was the first test of that claim — see the section below.

---

## MLS

Research date: August 2026, driven by the one attended MLS game blocking
`SP3_open_issues.md` #1b. **Built 2026-08-01**
(`backend/sports_passport/services/adapters/mls.py`). Unlike the original passes
above, every candidate here was tested against a live endpoint before being
ranked — the CBB research already showed how far docs-only conclusions can drift.

### TL;DR — Recommended Pick

| League | Historical Load (one-time) | Ongoing Updates (free) | Paid Fallback |
|--------|---------------------------|------------------------|---------------|
| MLS | ASA API 2013+, Kaggle `matches.csv` for 1996-2012 | ASA `/mls/games` | SportsDataIO / Sportmonks |

### Suggested Free (Historical + Ongoing): American Soccer Analysis

[American Soccer Analysis](https://app.americansocceranalysis.com/api/v1/__docs__/)
(`app.americansocceranalysis.com/api/v1/mls`) — free, keyless, and the best-fitting
source for this app of any league researched in this document. Live-verified
2026-08-01:

- **5,732 games, 2013-2026**, one request per season. Zero unresolved team ids,
  zero null scores, zero null dates. 2013 is a hard floor; 2012 and earlier return `[]`.
- **`date_time_utc` is genuinely UTC**, cross-checked against ESPN on a real game.
  So MLS needs none of the Eastern→UTC conversion that issue #7 forced on NBA/NFL.
- **`/mls/stadia` carries latitude, longitude, city, province and capacity** —
  the *only* source in this project that supplies venue coordinates directly. NFL,
  NHL and NBA all needed hand-built seed CSVs; MLS's modern era needed none.
- `/mls/teams` includes defunct clubs (Chivas USA), and games carry `attendance`
  and a `knockout_game` flag that maps straight onto `season_type`.

Two limitations, both real: **coverage starts at 2013**, and **only completed games
are published** (every row's status is `FullTime`), so there are no upcoming fixtures.

### Suggested Free (1996-2012 gap): Kaggle "Major League Soccer Dataset"

[josephvm's dataset](https://www.kaggle.com/datasets/josephvm/major-league-soccer-dataset)
— `matches.csv`, 7,289 rows, downloadable anonymously (no Kaggle auth needed).
Fills the 17 seasons ASA does not reach.

**Validated against ASA on the 2013-2022 overlap before being trusted.** All ten
overlapping seasons, Kaggle vs ASA:

| | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Kaggle | 338 | 338 | 357 | 357 | 391 | 408 | 421 | 324 | 472 | 281 | **3,687** |
| ASA | 338 | 338 | 357 | 357 | 391 | 408 | 421 | 324 | 472 | 489 | 3,895 |

Counts match exactly for 2013-2021, and **all 3,687 Kaggle rows find an ASA twin**
on date ±1 + score. 2022 is the one gap, and it is a Kaggle limitation rather than
a disagreement: the dataset stops mid-season at 281 of that year's 489 games. Since
ASA owns every season from 2013 on, none of these rows are imported anyway — the
overlap exists purely to establish whether the pre-2013 half can be trusted.

How that reconciles with the 9,333 games actually imported:

```
7,289  rows in matches.csv
-3,687  seasons 2013-2022, superseded by ASA
=3,602  rows before 2013
    -1  the 2004 All-Star game (an exhibition, not a club fixture)
=3,601  imported from Kaggle
+5,732  imported from ASA (2013-2026)
=9,333
```

The game set and scores are sound. The metadata is not uniformly so, and the
adapter compensates:

| Field | Coverage 1996-2012 | Handling |
|---|---|---|
| Scores | 100% | used as-is |
| Venue | 87% | 2001-03 is nearly empty; those games get a null venue |
| Kickoff time | 73%, and only **80.6% accurate** where present | discarded — era imports date-only |
| Attendance | 43% | used where present |
| Stable `id` | 73% | natural key `(date, home, away)`, verified unique |

Two traps worth recording. The `time (utc)` column's errors scatter ±30-210 minutes
rather than forming a timezone offset, so it is noise, not a fixable shift. And the
`date` column is the **local** game day, not UTC — 93.5% of games kicking off
00:00-05:59 UTC carry a Kaggle date one day earlier. Reading it as UTC would have
shifted every late kickoff forward a day, the exact bug class of issues #5 and #7.

### Rejected: ESPN for the historical load

Tempting, since ESPN is already wired in for NBA sync and logos, and its MLS
scoreboard does reach back to 2001. Two disqualifiers:

- **No venue before 2004.** Live sweep by year: June 2001 returned 30 events with
  **1** venue name; 2002 and 2003 returned **zero**; 2004 onward is ~100%. Venue is
  the field this app exists for. (The Kaggle file has the same 2001-03 hole, which
  suggests a shared origin.)
- **It would be a bulk crawl** — ~250 monthly requests for 2004-2026 — against this
  project's own rule that ESPN's hidden API is *never* used in bulk. ASA's entire
  backfill is 14 requests to an API built to serve them.

ESPN also reports venues under their *current* name ("Sports Illustrated Stadium"
for a 2015 game at Red Bull Arena), which reads worse on a venue-stamp page.

### All MLS sources found

| # | Source | Coverage | Cost | Notes |
|---|--------|----------|------|-------|
| 1 | [American Soccer Analysis](https://app.americansocceranalysis.com/api/v1/__docs__/) | 2013–present | Free, keyless | **The pick.** UTC-native, coordinates included, complete slate per season |
| 2 | [Kaggle MLS Dataset (josephvm)](https://www.kaggle.com/datasets/josephvm/major-league-soccer-dataset) | 1996–2022 (2022 partial) | Free | **The gap-filler.** Validated against #1; stale since 2022, so historical use only |
| 3 | [ESPN hidden API](https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard) | 2001–present; venues 2004+ | Free (unofficial) | Rejected for backfill (see above); does carry future fixtures if those are ever wanted |
| 4 | [openfootball/world](https://github.com/openfootball/world) | 2005–2025 | Free, public domain | Football.TXT format, clean licensing, but **no venue data** — nothing #1+#2 don't do better |
| 5 | [TheSportsDB](https://www.thesportsdb.com/) | Fixtures/results, thin history | Free / ~$9 Patreon | Fine for logos/metadata; not a historical backbone |
| 6 | [Sportmonks MLS](https://www.sportmonks.com/football-api/mls-api/) | Deep | Paid | Commercial-grade |
| 7 | [SportsDataIO Soccer](https://sportsdata.io/soccer-api) | Deep | Paid, contact sales | The standing paid fallback across this doc |
| 8 | [Enetpulse MLS](https://enetpulse.com/mls-api/) | Deep | Paid | Commercial-grade |
| 9 | [Statorium MLS](https://statorium.com/major-league-soccer-api) | Varies | Freemium | Nothing over #1 |
| 10 | [FBref](https://fbref.com/) | 1996–present | Free to browse; **no bulk/scrape** | **Off limits** — a Sports-Reference property, same project-wide prohibition |

### Compliance note

ASA publishes **no formal terms of service or license** — the OpenAPI spec carries
`license: None` and `termsOfService: None`. Mitigating that, ASA themselves maintain
the MIT-licensed [`itscalledsoccer`](https://pypi.org/project/itscalledsoccer/)
Python and R clients against this same API, so programmatic access is plainly
intended. Treated with the same posture as ESPN: descriptive User-Agent, polite
pacing, and a backfill that is 14 requests rather than a crawl.
