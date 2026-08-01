# SP3 Open Issues

Known data gaps and defects, discovered while importing the attendance history from
`Bronner Sporting Venues - Raw Sportspassport.csv` (2026-07-15). Each issue lists the
specifics needed to fix it without re-deriving the investigation.

## 1. Attended games that cannot be logged (2)

The attendance-history imports (user_id 2) from
`Bronner Sporting Venues - Raw Sportspassport.csv` (161 rows) and
`Bronner Sporting Venues - Unlogged Events.csv` (69 rows) matched every row to a
game in the DB except these 2, which have no `games` row to attach attendance to:

| # | Date | Game | Venue | Final | Blocker |
|---|------|------|-------|-------|---------|
| 1 | 2015-05-10 | New York City FC @ New York Red Bulls | Red Bull Arena | Red Bulls 2, NYCFC 1 | ~~MLS league not in DB~~ — **resolved 2026-08-01, see 1b** |
| 2 | 2025-03-23 | Tampa Bay Rays @ New York Yankees — **spring training** | George M. Steinbrenner Field | — | No spring-training data |

Row 1 is now logged; **row 2 is the only remaining unloggable attended game.**

### 1a. MLB postseason games — **RESOLVED 2026-07-15**

Two attended games were originally blocked here (2003 World Series Game 1 and
2017 ALCS Game 5, both at Yankee Stadium). Retrosheet turned out to publish
postseason gamelogs in the same fixed-field CSV format as the season files
(glws/gllc/gldv/glwc.zip — one all-years file per series type). Added
`MlbAdapter.import_postseason(start_season, end_season)` (wired into
`import_historical`, unit-tested), backfilled 1970–2025 into the live DB —
**1,483 postseason games, 0 errors** — and logged attendance on both games.
Pre-1970 postseason (back to the 1903 World Series) is available in the same
files if regular-season coverage is ever extended earlier.

### 1b. MLS not supported (row 1) — **RESOLVED 2026-08-01**

Seeded an `MLS` league and built `services/adapters/mls.py` on two sources split at
a hard season boundary, then logged attendance for user_id 2 on the game above
(attendance id 238, game id 500952 — NYCFC @ NY Red Bulls 1-2 at Red Bull Arena,
Harrison NJ). See `docs/SP3_data_sources.md` for the source research.

- **2013-present: American Soccer Analysis** (`app.americansocceranalysis.com`,
  free, keyless) is authoritative for teams, venues, games and sync. One request
  per season returns the complete slate, `date_time_utc` is genuinely UTC
  (cross-checked against ESPN), and `stadia` carries latitude/longitude directly —
  the only source in this project that supplies venue coordinates, so the modern
  era needed no hand-built seed.
- **1996-2012: the Kaggle "Major League Soccer Dataset"** (josephvm) fills the
  17 seasons ASA does not reach. Validated against ASA on the 2013-2022 overlap:
  per-season counts match exactly and all 3,687 rows find an ASA twin.

Imported **9,333 games (3,601 Kaggle + 5,732 ASA), 33 teams, 75 venues, 0 errors**,
seasons 1996-2026 continuous, **0 venues without coordinates**. Verified against a
pre-import backup (`sports_passport.pre-mls.db`, gitignored): no pre-existing game
or attendance row changed, `integrity_check` and `foreign_key_check` clean.

Three things worth knowing about the result:

- **The Kaggle era is date-only** (`has_time=False`, 3,601 rows). Its `time (utc)`
  column is present on only 73% of rows and, where present, agrees with ASA exactly
  80.6% of the time — the remainder scatters ±30-210 minutes, which is noise, not a
  timezone offset. Its `date` column is the *local* game day, confirmed because
  93.5% of games kicking off 00:00-05:59 UTC carry a Kaggle date one day earlier;
  reading it as UTC would have shifted every late kickoff forward a day, the bug
  class of issues #5 and #7.
- **474 games have no venue** — 453 from 2001-2003, where the Kaggle file carries
  almost none (2002 has zero). ESPN has the identical hole, suggesting a common
  origin, so it is not fixable from either source. Those games are still logged and
  searchable; they just contribute nothing to venue stamps or the map.
- **No upcoming fixtures.** Every ASA game has status `FullTime` — ASA publishes
  results, not schedules. So MLS shows completed games only, unlike CFB/CBB/NHL.
  ESPN does carry MLS fixtures if this ever matters; a rolling ~30-day window would
  be a legitimately non-bulk use of it.

### 1c. MLB spring training (row 2)

- Neither data path covers spring training: Retrosheet game logs are regular season
  only, and the MLB Stats API sync deliberately skips exhibition games —
  `STATSAPI_GAME_TYPES` in `backend/sports_passport/services/adapters/mlb.py` maps
  only `R/F/D/L/W` and drops gameType `S` (spring training).
- **If we decide to support it**: the MLB Stats API schedule endpoint does return
  spring-training games (`gameType=S`), so the fix is adding `"S": "spring"` to
  `STATSAPI_GAME_TYPES` (plus a `season_type='spring'` convention) and fetching the
  specific dates needed — small "since date" queries are compliant; bulk backfill
  via the Stats API is not (SP3_data_sources.md). Spring-training venues
  (e.g. Steinbrenner Field) would also be new `venues` rows.
- **Undecided** whether spring training even belongs in the passport (it would count
  toward venue/stamp stats). Only one attended game is affected, so deferred.
- After any import, log attendance for user_id 2 on the game above.

## 2. Can't tell CFB and CBB teams apart in the all-leagues view — **RESOLVED 2026-07-25**

When browsing/searching teams with the league filter set to all leagues, college
football and college basketball teams were indistinguishable: the same school appeared
twice with the same name (e.g. two "Alabama Crimson Tide" entries — one CFB, one CBB)
and nothing in the list indicated which league a given entry belonged to. Noted
2026-07-15.

Partly addressed by the frontend rebuild — omnibox results are grouped under a
league header (`Omnibox.tsx`) and TeamDetail prints the league code — but the
"Your teams" chips on Find and the game rows on My log still showed nothing but
a name and a logo, and a school's CFB and CBB rows often share both.

**Fix**: `TeamBadge` renders a small basketball marker on the bottom-right corner
of the team icon when `leagueCode === 'CBB'`, ringed in `var(--panel)` so it stays
legible over a busy logo. The marker is absolutely positioned inside a wrapper the
size of the badge, so no layout box changes; the slight overhang is kept under the
6px badge-to-name gap used by the tightest rows. Every surface that shows a team
icon goes through `TeamBadge`, so the one change covers Find, the omnibox, My log
and TeamDetail. CFB is left unmarked — it's the default reading of a college team
here, and marking only the exception keeps the lists quiet.

## 3. MLB team naming: "St. Louis Browns" is really the Cardinals — **RESOLVED 2026-07-15**

Fixed in `MLBAdapter.import_teams` (parse era start dates before sorting instead of
lexicographic string sort) and `import_teams` re-run against the live DB. All four
rows below now carry their current-era names (SLN → Cardinals, PHI → Phillies,
CLE → Guardians); the SLA row (the real 1902–1953 Browns) was untouched, and the
full test suite passed (158/158 at the time of this fix; see the PR description
for the current count). "Sacramento Athletics" turned out to be exactly
what Retrosheet's CurrentNames.csv provides for the ATH era — source data, not a bug.

Known nuance of the one-row-per-Retrosheet-code design: a code's games from *all*
eras display under the latest era's name (e.g. 2018 Cleveland games render as
"Guardians"). Era-accurate names would need one team row per era row, which
Retrosheet provides — only worth doing if it ever bothers anyone.

Original write-up follows for reference.

### Symptom

The Cardinals' team row (`teams.id = 173`, `source_team_id = 'SLN'`, `last_season = NULL`)
is named **"St. Louis Browns" / nickname "Browns"** — the franchise's 1882 founding name.
All 8,900+ SLN games across every era display under that name; e.g. the logged
2018-09-28 game at Wrigley Field (game id 300635, Retrosheet id `20180928_SLN_CHN_0`)
renders as "St. Louis Browns @ Chicago Cubs" instead of "St. Louis Cardinals".
The game rows themselves are correct — this is purely a team-name defect.

Note there is *also* a legitimate "St. Louis Browns" row (`teams.id = 135`,
`source_team_id = 'SLA'`, 1902–1953, the AL franchise that became the Orioles).
Any fix must not touch that row.

### Other franchises affected (all `last_season IS NULL` rows checked 2026-07-15)

| teams.id | source_team_id | Current name in DB | Should be |
|----------|----------------|--------------------|-----------|
| 173 | SLN | St. Louis Browns | St. Louis Cardinals |
| 166 | PHI | Philadelphia Quakers | Philadelphia Phillies |
| 144 | CLE | Cleveland Indians | Cleveland Guardians |
| 165 | ATH | Sacramento Athletics | Athletics (verify vs. Retrosheet's city/era data) |

### Root cause

`MLBAdapter.import_teams` (`backend/sports_passport/services/adapters/mlb.py:109`)
picks each team code's "latest" era row by sorting the era rows **lexicographically on a
`M/D/YYYY` date string**:

```python
code_rows.sort(key=lambda r: r[7])  # ascending by start date  <-- string sort, not date sort
latest = code_rows[-1]
```

`"5/2/1882"` (Browns era) sorts *after* `"4/19/1900"` (Cardinals era) because `'5' > '4'`,
so the 1882 era wins and its name is written to the team row. Same mechanism for
PHI (Quakers era starts in May). CLE/ATH should be re-verified after the sort is fixed —
they may have an additional wrinkle (e.g. import ran against older source data).

### Fix

1. Parse `r[7]` to a real date before sorting (e.g. `_parse_mdy(...)`), or sort on
   `(year, month, day)`.
2. Re-run `import_teams` for MLB — `upsert_team` is keyed on `(source, source_team_id)`
   so the existing rows update in place; no game rows change.
3. Verify the four rows above, and confirm era-scoped rows with `last_season` set
   render correctly (they should, since they don't participate in the "latest era" sort).

## 4. Ruff B008: `Depends()` in argument defaults (admin router) — deferred

CodeRabbit's PR #3 review flagged `Depends(get_db)` / `Depends(get_current_admin_user)`
as function-call-in-default-argument (Ruff B008) on the `sync-all` endpoint. Left as-is:
it's the existing pattern across every endpoint in `admin.py` (and the other routers),
not something newly introduced by that PR, so fixing it there alone would be
inconsistent without a codebase-wide pass. Worth a dedicated cleanup pass across all
routers if it's ever enforced in CI.
   (e.g. Florida Marlins `FLO`, St. Louis Browns `SLA`) are untouched.

## 5. CFB (and other late-kickoff) games displaying a day late — **RESOLVED 2026-07-17**

Some games with late US kickoffs (e.g. a 7:30 PM ET Saturday game, which is after
midnight UTC) displayed as the day *after* they were actually played — reported
example: Alabama @ LSU, played Sat 2024-11-09, showing as "Nov 10, 2024".

The DB data was correct (`start_date` for that game is genuinely `2024-11-10
00:30:00` UTC — 7:30 PM ET on Nov 9). Two compounding bugs caused the wrong display:

1. The API serialized naive `datetime` fields (`start_date`, and
   `first_game_date`/`last_game_date` in attendance stats) without a UTC marker
   (e.g. `"2024-11-10T00:30:00"`, no `Z`/offset). Per the JS Date spec, a
   date-time string with no offset is parsed as the *browser's local time*, not
   UTC — so the absolute instant itself was wrong on any client not running in
   the UTC timezone, before timezone-of-display even entered the picture.
2. The frontend then always rendered dates in UTC to avoid rolling back the
   `has_time=false` bulk-imported rows (old Retrosheet MLB data, which only
   carry a naive midnight-UTC date with no real kickoff time) — but UTC is one
   calendar day ahead of the correct US game day for any kickoff after ~7-8 PM
   Eastern.

**Fix**: `naive_utc_isoformat` (`backend/sports_passport/core/serializers.py`)
attaches an explicit UTC offset when serializing these fields, applied via
`field_serializer` on `GameBase`/`GameListResponse.start_date` and
`AttendanceStats.first_game_date`/`last_game_date`. The frontend
(`frontend/src/utils/format.ts`) now renders `has_time=true` games in the
viewer's own local timezone (no explicit `timeZone` override) and keeps
`has_time=false` rows pinned to UTC. Very late West Coast/Hawaii kickoffs that
themselves cross midnight in the viewer's local timezone are a known remaining
edge case, not fully solvable without per-venue timezone data — see issue #7,
which quantifies it and confirms it now applies uniformly across all leagues.

## 6. `alembic upgrade head` fails from every database state — **RESOLVED 2026-07-23**

Discovered 2026-07-23 while verifying the attendance unique-constraint migration
(`f3a9d4b6c281`) on branch `opencode-fixes-7-23`.

The initial migration `9182bb4bc1d2` ("initial multi-league schema") is an empty
`pass` stub — the schema has only ever been created by
`Base.metadata.create_all()` at import time in `main.py`, with every later
migration `ALTER TABLE`-ing on top of it. That leaves two authorities for one
schema: `create_all` always builds the *current* models, while `alembic_version`
records a history that never created anything. Migrations then fail in both
directions — "no such table" on an empty database, "already exists" on a
populated one.

Reproduced 2026-07-23 by scripted runs against each real state:

| State | Where it exists | Failure |
|---|---|---|
| empty database | fresh deploy / new volume | `no such table: teams` at `9182bb4bc1d2 → b4c9e1f7a2d3` |
| stamped `c8e2f4a6b1d9` | `backend/deploy_sports_passport.db` | `table sync_state already exists` |
| stamped `a7e4c2f1b3d6` | `backend/sports_passport.db` (live dev DB) | `table password_reset_tokens already exists` |
| stamped `e2f5b8c3d4a1` | prior head | `index uq_user_game_attendance already exists` |

- The Dockerfile runs `alembic upgrade head && uvicorn ...`, so a container
  whose database is in any of these states will not start.
- The last row is a regression from this branch's `f3a9d4b6c281`: the index it
  creates is also built by `create_all` from the model's `__table_args__`. It
  survives a first container deploy only because migrations run before uvicorn
  imports `main.py` — ordering luck, not a guarantee.
### Fix applied (2026-07-23)

1. `sports_passport/db/migration_guards.py` — `has_table` / `has_column` /
   `has_index`, introspecting via `sa.inspect(op.get_bind())`. It lives in the
   app package because `backend/alembic/` has no `__init__.py`, so
   `from alembic.guards import ...` would resolve to the installed library.
2. `9182bb4bc1d2` backfilled with the real `create_table` calls for the six
   base tables, as of that revision (no `logo_url`, no venue coordinates, no
   `sync_state`, no `password_reset_tokens`, no attendance unique index).
3. All six later revisions made create-if-absent. Downgrades left unguarded —
   a downgrade is deliberate and should fail loudly.
4. `d1f3a7c9e5b2` corrected: it declared `sync_state.league_id` unique as a
   table constraint, but the model spells it `unique=True, index=True`, i.e. a
   unique index — so a migration-built database did not match a create_all-built
   one. Caught by the new schema-parity test, not by inspection.
5. `create_all()` removed from `main.py`. Alembic now owns the schema outright;
   a fresh database needs `alembic upgrade head` first (Docker already does it).
6. `tests/test_migrations.py` pins convergence from all five known states, that
   a populated database keeps its rows, and that a migration-built schema
   matches the models.
7. **A sixth state, missed on the first pass and found 2026-07-25** (via
   CodeRabbit on PR #6): a database *stamped at `9182bb4bc1d2` with no tables*.
   This is the wreckage the old chain left on every fresh deploy — the empty
   `pass` stub committed and stamped, then `b4c9e1f7a2d3` died at the first
   ALTER. Backfilling the root does not rescue it: Alembic sees such a database
   as already past that revision and restarts at `b4c9e1f7a2d3`, which meets a
   `teams` table nobody created. The table definitions therefore moved to
   `sports_passport/db/base_schema.py`, and `b4c9e1f7a2d3` calls
   `create_base_schema()` before altering anything. The original test matrix
   covered "empty and unstamped" but never "stamped and empty", which is why it
   went unnoticed.

   Note the deliberate boundary: an empty database *manually* stamped at some
   mid-chain revision still fails, and should. That is operator error, and
   silently reconstructing a schema underneath it would hide the mistake rather
   than surface it.
8. Two more drifts caught once the parity check was widened to compare column
   defaults and foreign keys, not just names and types: `sync_state.enabled`
   and `password_reset_tokens.used` carry a `server_default` in their
   migrations that the models never declared. The models now declare it, so
   `create_all` matches both the migrations and every live database — the
   alternative, dropping it from the migrations, would need a SQLite table
   rebuild to change a column default on databases that already have it.

**Applied to the live database** (496,382 games / 237 attendance rows): backed
up first with SQLite's own `.backup` (WAL-safe, unlike `cp`), rehearsed on the
copy, then upgraded `e2f5b8c3d4a1 → f3a9d4b6c281`. Row counts, per-user
attendance, `integrity_check` and `foreign_key_check` all identical afterwards;
the only changes are the version stamp and the new unique index. Backup kept at
`backend/sports_passport.pre-f3a9d4b6c281.db` (gitignored).

## 7. NBA and NFL `start_date` held Eastern, not UTC — **RESOLVED 2026-08-01**

Raised by CodeRabbit on PR #9. `games.start_date` is documented as UTC
(`SP3_plan.md` §3), `core/serializers.py` stamps a UTC offset on it, and the
frontend renders `has_time = true` rows in the viewer's timezone (issue #5).
Two bulk paths broke that contract by writing a naive **US Eastern** wall
clock into the column: the NBA Kaggle `Games.csv` (`gameDate`) and nflverse
(`gameday` + `gametime`). NFL was the wider gap — it was never recorded here,
and `nfl.py`'s docstring described storing Eastern as-is as a deliberate
"good enough" allowance, which stopped being true once issue #5 made the API
assert an explicit UTC offset.

### What the source data actually is

The original write-up assumed the NBA times were *arena-local*. They are not,
and the distinction matters: converting arena-local would have been three
hours wrong for every western venue. Two independent checks, both against the
loaded database:

- Modal tip-off by venue timezone, NBA 1996+: Eastern arenas 19:00/19:30,
  Central 20:00/20:30, Mountain 21:00, Pacific 22:00/22:30 — every zone peaks
  at 7:00–7:30pm *local*, expressed in Eastern. Stable across 1996–2004,
  2005–2014 and 2015–2025.
- NFL west-coast home games cluster at 16:05/16:25, i.e. the 1:05/1:25pm PT
  windows in Eastern.

Confirmed against ESPN on two real rows:

| Game | Stored (before) | ESPN | Stored (after) |
|---|---|---|---|
| `22500795` Pacers @ Wizards (ET venue) | `2026-02-19 19:00` | `2026-02-20T00:00Z` | `2026-02-20 00:00` |
| `22500696` Pistons @ Warriors (PT venue) | `2026-01-30 22:00` | `2026-01-31T03:00Z` | `2026-01-31 03:00` |

The Warriors row is the decisive one: 22:00 is 10:00pm **Eastern**, not
10:00pm Pacific.

### Fix

`services/adapters/local_time.py` — `to_utc(naive, zone=EASTERN)`, using
`zoneinfo` so the DST offset is the one in effect on that date. Applied in
`nfl.py::_parse_start` and `nba.py::_upsert_row`. No per-venue timezone data
is involved, because neither source needs it; the venue timezone column
floated in the original write-up would have been both more work and, for
these two sources, wrong.

`FIRST_SEASON_WITH_REAL_TIMES` also moved 1969 → 1996. The CSV has no real
tip-offs before then: every season 1969–1995 carries one or two distinct
clock values for the *entire year* (almost all 7:00 or 8:00pm), while 1996+
has 20–29 distinct tip-offs a season. Those 26,425 rows now go in with
`has_time = False` at naive midnight, so the UI shows their date and stops
implying a precision the source never had. NBA `has_time = 1` rows therefore
drop 66,319 → 39,894.

Backfill: migration `c4d8e2a1f7b3`, applied to the live database
(496,382 games / 237 attendance rows) after a WAL-safe `.backup` rehearsal;
row counts, attendance, `integrity_check` and `foreign_key_check` all
identical afterwards. Backup at `backend/sports_passport.pre-c4d8e2a1f7b3.db`
(gitignored). The migration is deliberately **not reversible** — the pre-1996
placeholder times it discards are not recoverable.

### Verified effect on what users see

The frontend renders dates only (it has no clock-time formatter at all), so
the check that matters is whether any game's displayed calendar day moved.
Across all 80,820 NBA + NFL rows:

| Viewer timezone | Displayed date changed |
|---|---|
| US Eastern | 14 |
| US Central | 11 |
| US Pacific | 6 |
| Sydney | 28,005 |

All 237 attended games are unchanged in every US zone. The 14 Eastern changes
are all October preseason games played abroad (NBA Global Games) that
genuinely tip between 00:00 and 02:00 ET. The Sydney column is the bug being
fixed: viewers east of UTC were seeing tens of thousands of games on the
wrong day.

NBA's rate of "ET-rendered date differs from the venue-local game day" is now
0.03%, against CBB 0.13% and CFB 0.58% — i.e. in line with the leagues that
were already storing UTC correctly.

### Known remaining issue

The residual is issue #5's unchanged edge case, now shared uniformly by every
league: a game that crosses midnight in the *viewer's* timezone displays on
the following calendar day, because the frontend renders in viewer-local time
and the app has no notion of the venue's local "game day". A late West Coast
game viewed from the East Coast is the common instance; the 14 rows above are
the extreme one. Closing it properly means displaying each game's date in its
*venue's* timezone rather than the viewer's — which is the point at which a
real timezone column on `venues` would earn its keep. Not worth it for a
handful of rows today.

Two smaller things deliberately left alone:

- CFB sets `has_time=True` unconditionally (`cfb.py:146`) where CBB gates on
  `startTimeTbd`, so ~518 unscheduled 2026 games publish CFBD's midnight-ET
  placeholder as though it were a real kickoff. Harmless while no clock time
  is displayed.
- NBA seasons 1973 and 1975 have 17 and 24 distinct clock values against 1–2
  for every other pre-1996 season, so the Kaggle source may carry partially
  real times for those two years. They fall below the 1996 cutoff and are
  treated as time-less like the rest.

## 8. Date-only games sat at midnight, one bug away from displaying a day early — **RESOLVED 2026-08-01**

A `has_time=False` row carries a calendar game day and no real kickoff, so its
time-of-day is a storage detail. Midnight was the wrong default for it.

Midnight UTC only ever displayed correctly because the frontend pins
`has_time=False` rows to UTC (`displayTimeZone` in `frontend/src/utils/format.ts`).
That pin is one line, and *every* consumer has to remember it: a new component, a
CSV export, a chart, a third-party reader of the API. Forget it anywhere and
midnight UTC renders as the **previous calendar day** everywhere west of
Greenwich — which is the entire United States. The data was correct; it was
correct by convention rather than by construction, and the convention had no
enforcement.

**Fix**: `local_time.date_only()` parks date-only games at **noon** UTC
(`DATE_ONLY_HOUR = 12`), which lands on the right calendar day for every offset
from UTC-11 through UTC+11. A consumer that forgets the pin now gets the right
answer anyway. The helper is shared, so the choice lives in one place rather than
being restated in each adapter — MLB, NFL, NBA and CBB all call it, and MLS was
built on it.

Migration `a9f2c7e4b8d1` moved every existing date-only row. It cannot change a
displayed date by construction: it only rewrites the time *within* each row's
existing UTC date, and those rows render on that UTC date. Verified against a
pre-migration backup of the live database (496,412 games / 237 attendance rows):

| Check | Result |
|---|---|
| Games whose UTC calendar date changed | **0** |
| Games whose `has_time` changed | **0** |
| `has_time=True` rows whose instant moved | **0** |
| Date-only rows now at `12:00:00` | 206,990 of 206,990 |

Row counts, attendance, `integrity_check` and `foreign_key_check` all identical
afterwards. Backup at `backend/sports_passport.pre-a9f2c7e4b8d1.db` (gitignored).

The downgrade returns every date-only row to midnight uniformly. That is exact
for all but 15 CBB rows, which sat at 17:00 rather than midnight — CBBD noon-ET
placeholders on `startTimeTbd` games. They were never real tip-off times, which
is why those rows are `has_time=False` to begin with.

**Note this does not close issue #5's edge case**, which is about `has_time=True`
rows and is unaffected: a game crossing midnight in the *viewer's* timezone still
displays on the following day. Closing that still means rendering in the venue's
timezone.
