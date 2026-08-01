# NFL backfill to 1970 — plan

Goal: close the NFL's 1970–1998 gap (the `docs/SP3_open_issues.md` deferral recorded in
`adapters/nfl.py`'s docstring) with a **one-time bulk load**, leaving nflverse as the sole
owner of 1999-present and of ongoing sync.

## Source decision

**Kaggle "NFL scores and betting data" (`tobycrabtree`), `spreadspoke_scores.csv`.**
The 2026-07-11 deferral said this file now sits behind a Kaggle login. **That is no longer
true** — verified 2026-08-01, the public download API serves it unauthenticated:

```bash
curl -L -o nfl.zip https://www.kaggle.com/api/v1/datasets/download/tobycrabtree/nfl-scores-and-betting-data
```

(`HEAD` on that URL 404s; only `GET` works. 263 KB zip → `spreadspoke_scores.csv`, `nfl_teams.csv`.)
Same access pattern as the MLS Kaggle file, so `docs/SP3_data_sources.md`'s NFL note needs
correcting rather than the league staying deferred.

### Validation performed (2026-08-01)

| Check | Result |
|---|---|
| Coverage | 1966–2025, 14,371 games; **6,367 in 1970–1998** |
| Nulls in date / both scores / stadium | **0** |
| Date parse (`%m/%d/%Y`) failures | **0** |
| Duplicate `(date, home, away)` keys | **0** — natural key is safe |
| Per-season counts | Match reality exactly, incl. 1982 strike (141), 1987 strike (177), 1978 16-game expansion (233), 1993's 18 weeks, 1995 expansion (251) |
| **Game set vs nflverse, 1999–2024** | **6,991 vs 6,991, zero per-season variance** |
| Playoff labelling | `schedule_week` ∈ {Wildcard, Division, Conference, Superbowl} ⇔ `schedule_playoff=TRUE`; no numeric week mis-flagged |
| Neutral sites 1970–1998 | 29 games, flagged via `stadium_neutral` |

Franchise moves are right down to the season: Ravens at Memorial 1996–97 then M&T 1998;
Rams split 1995 between Busch (4) and the Edward Jones Dome (4); Packers' Milwaukee County
Stadium split every year to 1994; Oilers at the Liberty Bowl 1997 then Vanderbilt 1998.

**Sources rejected:** ESPN core API returns 0 events for 1970 and is bulk-barred by our
compliance rules anyway; Pro-Football-Reference is Sports-Reference (barred); FiveThirtyEight's
elo CSV covers 1920+ but carries **no venue**, which is the whole point of this app.

## Known defects and how each is handled

1. **Arizona Cardinals 1994–1998 home games are labelled "University of Phoenix Stadium"**
   (40 games) — that building opened in 2006; they played at Sun Devil Stadium. The 1988–93
   "Phoenix Cardinals" rows correctly say Sun Devil. Independently confirmed on the 1999+
   overlap, where 55 rows under that name resolve to `PHO99`. Fix: home team ARI/PHO and
   season < 1999 ⇒ force `PHO99`.
2. **The `stadium` column is a physical-building name, not the name of the era** — it applies
   one modern name across a building's whole life ("Cinergy Field" for Riverfront,
   "Ralph Wilson Stadium" for Rich, "Sun Life Stadium" for Joe Robbie). This is *helpful*:
   it behaves like a stable venue key, which is exactly what `venue_seed` wants. But a
   handful of rows use the era name instead ("Jack Murphy Stadium" ×1, "Joe Robbie" ×2,
   "Pro Player" ×1, "Tampa Stadium" ×2), so an alias map is still required.
3. **No kickoff times at all.** Whole era imports `has_time=False` via `local_time.date_only()`
   — the same call the MLS Kaggle era and NBA pre-1996 make (open issue #8).
4. **No attendance column.** Pre-1999 games import with `attendance=None`.
5. **No overtime column.** `overtime_flag` stays `None` for the era.

## Design

Mirror `mls.py` exactly — two sources on one adapter, split at a hard season boundary:

- `FIRST_NFLVERSE_SEASON = 1999`. nflverse is never asked for a season below it; spreadspoke
  rows at or above it are skipped. The boundary is on **season**, not date, so the Jan-1999
  playoffs of the 1998 season land on the spreadspoke side with the rest of their season.
- **`source` stays `"nflverse"`.** Not cosmetic: 31 of the 64 pre-1999 stadiums resolve to
  `stadium_id`s already in `nfl_stadiums.csv`, and `upsert_venue` keys on `(source,
  source_venue_id)` — a new source string would mint a second Three Rivers Stadium rather
  than joining the existing row. Pre-1999 game ids get a `spreadspoke-` prefix
  (`spreadspoke-1972-12-23-pit-oak`), the way the MLS era uses `kaggle-`.
- Bulk file at `backend/data/raw/nfl/spreadspoke_scores.csv` (gitignored), with the same
  `FileNotFoundError`-with-curl-command guard `mls.py::_read_matches_csv` uses.

### Team identity

31 of the 38 era team names map onto abbreviations nflverse already uses (`WAS` covers
Redskins, `OAK` covers 1970–81 and 1995+, `CLE` covers the pre-1996 Browns, `SD`, `STL`).
**7 need new rows**, each because the obvious abbreviation is taken by a different modern club:

| Spreadspoke name | New `source_team_id` | Blocked by |
|---|---|---|
| Baltimore Colts | `BAL-COLTS` | `BAL` = Ravens |
| St. Louis Cardinals | `STL-CARDS` | `STL` = Rams |
| Houston Oilers | `HOU-OILERS` | `HOU` = Texans |
| Tennessee Oilers | `TEN-OILERS` | `TEN` = Titans |
| Los Angeles Raiders | `LA-RAIDERS` | `LA` = Rams 2016–19 |
| Phoenix Cardinals | `PHO` | (free) |
| Boston Patriots | `BOS` | (free) |

`franchise_id` for each comes from the modern successor's `nfl_team_id`, via
`nfl_teams.csv`'s `team_id` column — so the passport still reads Oilers→Titans as one
franchise, matching the existing STL/LA Rams treatment.

### Venue

- **31 of 64** pre-1999 stadiums resolve to an existing seeded `stadium_id`, derived
  empirically from the 1999+ overlap (matched on date + both scores). Those games join
  venue rows the app already has — no new seed entries, and the map atlas keeps one pin
  per building.
- **29 new seed rows** needed in `nfl_stadiums.csv` (1,925 games), ids prefixed `hist-` so
  they can never collide with a future real nflverse id: RFK, Astrodome, Cleveland
  Municipal, Tampa Stadium, Atlanta-Fulton County, Orange Bowl, Busch Memorial, Anaheim,
  Memorial Stadium (Baltimore), Metropolitan, Milwaukee County, Shea, Tulane, Tiger Stadium
  (Detroit), Yankee Stadium, War Memorial, Cotton Bowl, Yale Bowl, Kezar, Memorial Stadium
  (Clemson), Liberty Bowl, Vanderbilt, Harvard, Wrigley, Kansas City Municipal, Rose Bowl,
  California Memorial, Rice, Stanford. Each needs city / 2-letter state / lat-lon
  (`venues.state` must stay a 2-letter code — the attendance stats group on it directly).
- **4 alias-only** entries onto rows that already exist: Houlihan's Stadium + "Tampa Stadium"
  → one `hist-tampa-stadium`; "Joe Robbie Stadium" and "Pro Player Stadium" → `MIA00`;
  "Jack Murphy Stadium" → `SDG00`.

## Tasks

- [ ] Correct the NFL entries in `docs/SP3_data_sources.md` and the `adapters/nfl.py`
      docstring — the Kaggle file is reachable again; drop the "deferred" framing.
- [ ] Add `backend/data/raw/nfl/` to the gitignore alongside the MLS raw path; download the file.
- [ ] Add 29 rows to `sports_passport/data/seed/nfl_stadiums.csv` with hand-verified
      city/state/lat-lon.
- [ ] `nfl.py`: add `FIRST_NFLVERSE_SEASON`, `SPREADSPOKE_TEAM_ALIASES` (38 names → abbrev),
      `HISTORICAL_TEAMS` (the 7 above), `SPREADSPOKE_VENUE_IDS` (64 names → stadium_id),
      and the Cardinals/Sun Devil override.
- [ ] `nfl.py`: `_read_spreadspoke_csv()` + `_import_spreadspoke()`; route
      `import_historical` by the boundary. `sync_recent` is untouched — it stays nflverse-only.
- [ ] `import_teams` must mint the 7 historical rows and widen `first_season` on the ~31
      shared abbreviations (currently derived from nflverse games only, so every pre-1999
      club would still claim `first_season=1999`).
- [ ] Extend `tests/test_nfl_adapter.py`: boundary enforced in both directions, a
      spreadspoke row imports date-only with `has_time=False`, the Sun Devil override fires,
      an era team resolves to its own row not the modern one, and a shared-building row
      lands on the existing venue rather than creating a duplicate.
- [ ] Run the real import (`import_historical(1970, 1998)`), then verify: 6,367 games added,
      0 unmatched teams, 0 rows with a null venue, per-season counts match the table above,
      and no NFL venue row is duplicated by name.
- [ ] Update `docs/SP3_plan.md` Phase 4 + `CLAUDE.md`'s architecture note (NFL becomes the
      second two-source league).

## Decision

Built as an adapter (user's call, 2026-08-01) rather than a throwaway script.

## Review

All tasks above are done. Implemented on branch `nfl-1970-backfill`.

**Result — full 1970–2026 import, zero errors:**

| Source | Games | Seasons |
|--------|-------|---------|
| Spreadspoke | 6,367 | 1970–1998 |
| nflverse | 7,548 | 1999–2026 |
| **Total** | **13,915** | 42 teams, 91 venues |

Verified against the predictions in the plan:

- 6,367 historical games, **matching the expected per-season counts for all 29 seasons**
  (including the 1982 and 1987 strike years) with **0 errors, 0 unmatched teams, 0 games
  without a venue, 0 rows with a null score**.
- **Re-running the full range imports 0 and updates 13,915** — the seam is idempotent.
- **No duplicate venue names.** Buildings that span the boundary are a single row:
  Three Rivers Stadium 1970–2000, Lambeau Field 1970–2026, Soldier Field 1971–2026,
  Highmark Stadium (ex-Rich/Ralph Wilson) 1973–2026.
- The Cardinals defect is fixed — all 40 of their 1994–98 home games now sit at Sun Devil
  Stadium, which the override also reunites with the 1999–2005 nflverse rows on one venue
  row spanning 1988–2005.
- Franchise continuity reads correctly across the era split: Houston Oilers [1960–1996] →
  Tennessee Oilers [1997–1998] → Tennessee Titans [1999–] all share `franchise_id` 2100.
- Every venue state is a 2-letter code and **all 91 venues have coordinates**, so the
  attendance stats don't split a state and every historical ground plots on the map.
- Spot-checked against history: Super Bowl XX (Bears 46, Patriots 10, Superdome, neutral)
  and the oldest row in the database (1970-09-18, Cardinals 13 @ Rams 34, LA Memorial
  Coliseum) are both correct.
- **312 tests green** (was 298; +14 covering the new era).

**Two things that differed from the plan:**

1. `_team_lookup` had to be re-keyed from `abbreviation` to `source_team_id`. The plan
   didn't anticipate it: the historical era deliberately reuses abbreviations the modern
   league reassigned (the Oilers were "HOU", now the Texans), so the old abbreviation-keyed
   lookup would have let a defunct club shadow the modern one and misfile its games. There
   is no uniqueness constraint on `abbreviation` — it is display-only — so this was safe.
2. 59 distinct venues in the historical era rather than the 60 the plan implied: the Sun
   Devil override collapses "University of Phoenix Stadium" and "Sun Devil Stadium" onto
   one id.

**Known limitation, documented in the adapter and the plan:** a team's era is one
`(first_season, last_season)` span, so an identity used in two separate stretches now reads
as continuous — OAK (Oakland 1970–81 and 1995–2019) and CLE (the 1996–98 hiatus). Games are
attributed correctly; only the summary span overreaches. Narrowing it needs a schema change
to hold multiple ranges per team, which was out of scope here.
