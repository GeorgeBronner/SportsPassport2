# SP3 Open Issues

Known data gaps and defects, discovered while importing the attendance history from
`Bronner Sporting Venues - Raw Sportspassport.csv` (2026-07-15). Each issue lists the
specifics needed to fix it without re-deriving the investigation.

## 1. Attended games that cannot be logged (2)

The attendance-history imports (user_id 2, george.bronner@gmail.com) from
`Bronner Sporting Venues - Raw Sportspassport.csv` (161 rows) and
`Bronner Sporting Venues - Unlogged Events.csv` (69 rows) matched every row to a
game in the DB except these 2, which have no `games` row to attach attendance to:

| # | Date | Game | Venue | Final | Blocker |
|---|------|------|-------|-------|---------|
| 1 | 2015-05-10 | New York City FC @ New York Red Bulls | Red Bull Arena | Red Bulls 2, NYCFC 1 | MLS league not in DB |
| 2 | 2025-03-23 | Tampa Bay Rays @ New York Yankees — **spring training** | George M. Steinbrenner Field | — | No spring-training data |

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

### 1b. MLS not supported (row 1)

- `leagues` contains only CFB, MLB, NFL, NBA, NHL, CBB. There is no MLS seed row,
  no MLS adapter, and no MLS teams/games.
- **Fix** (per the architecture in CLAUDE.md, adding a league = one adapter module +
  one seed row): seed an `MLS` league, build an adapter in
  `services/adapters/`, register it in `adapters/__init__.py`, then import at least
  the 2015 season and log attendance for user_id 2 on the game above.
- Only one attended MLS game exists, so this is low priority; it mainly matters for
  venue/stamp completeness (Red Bull Arena).

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

## 2. Can't tell CFB and CBB teams apart in the all-leagues view

When browsing/searching teams with the league filter set to all leagues, college
football and college basketball teams are indistinguishable: the same school appears
twice with the same name (e.g. two "Alabama Crimson Tide" entries — one CFB, one CBB)
and nothing in the list indicates which league a given entry belongs to. Noted
2026-07-15; no solution designed yet.

## 3. MLB team naming: "St. Louis Browns" is really the Cardinals — **RESOLVED 2026-07-15**

Fixed in `MLBAdapter.import_teams` (parse era start dates before sorting instead of
lexicographic string sort) and `import_teams` re-run against the live DB. All four
rows below now carry their current-era names (SLN → Cardinals, PHI → Phillies,
CLE → Guardians); the SLA row (the real 1902–1953 Browns) was untouched, and the
full test suite passes (158/158). "Sacramento Athletics" turned out to be exactly
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
   (e.g. Florida Marlins `FLO`, St. Louis Browns `SLA`) are untouched.
