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
| 1 | [Kaggle NFL scores (Spreadspoke)](https://www.kaggle.com/datasets/tobycrabtree/nfl-scores-and-betting-data) | 1966–present | Free | One CSV, includes stadium + weather; ideal bulk load |
| 2 | [nflverse `games.csv`](https://github.com/nflverse/nfldata/blob/master/data/games.csv) | 1999–present | Free | Auto-updated; raw-URL fetch; ideal ongoing sync |
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

## Future League Expansion (MLS etc.)

- ESPN hidden API and TheSportsDB both already carry MLS (and most other leagues), so the
  ongoing-update adapter pattern extends naturally.
- MLS began in 1996, so "back to 1970" is moot; ESPN/TheSportsDB coverage plus a Kaggle or
  [FBref](https://fbref.com/)-derived historical file would follow the same
  bulk-load-then-sync pattern. (FBref is a Sports-Reference property — same scraping
  restrictions apply.)
- Same pattern works for WNBA, CFL, college basketball, etc. — the per-league adapter +
  common `games` schema is the design decision that makes this cheap.
