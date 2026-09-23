# NBA Sync Data Source — Fix Options

`NbaAdapter.sync_recent` (`backend/sports_passport/services/adapters/nba.py`) is broken again.
See `docs/open_issues.md` #15 for the full incident writeup — this doc is the options research
it points to, plus a plan for whichever option gets picked.

**Scope: forward-facing sync only.** NBA's 1946+ historical backfill is a one-time Kaggle CSV
import (`import_historical`, reads `backend/data/raw/nba/Games.csv`) and is untouched by any of
this — it doesn't call any live API and isn't affected by the outage below. Nothing here needs to
cover deep history; it only needs current-season schedule, final scores, and venue for recent and
upcoming games.

Research date: September 2026.

## The problem

This is the **second** NBA live-data source in a row to go dark the same way:

| Source | Status | When | Signature |
|---|---|---|---|
| `stats.nba.com` / `cdn.nba.com` | Dead | Abandoned 2026-08-01 | Akamai "Access Denied", from Oracle prod *and* a residential connection |
| ESPN hidden scoreboard (`site.api.espn.com`) | Dead | Discovered 2026-09-21 | Same Akamai "Access Denied" (`errors.edgesuite.net`), reproduced live from **both** Oracle prod and the `docker31` staging host |

Both are unofficial, reverse-engineered endpoints with no published terms — convenient until
Akamai's bot-management decides datacenter/cloud traffic isn't welcome, at which point there is no
header or IP change that fixes it (verified: two different hosts, both blocked identically). The
recommendation below weights *documented, publicly-supported* APIs over another unofficial one,
specifically because this project has now burned through two of the latter.

## Options considered

| Source | Access | Cost | Auth | Forward coverage | Rate limit | Cloud/datacenter IP risk |
|---|---|---|---|---|---|---|
| ESPN hidden API (current) | `site.api.espn.com` | Free | None | Schedule, scores, venue | Unofficial, unpublished | **Confirmed dead** — Akamai 403 |
| `stats.nba.com` / `cdn.nba.com` | Official hidden API | Free | None | Schedule, scores, venue | Unofficial | **Confirmed dead** — Akamai 403 (already known, see `nba.py` docstring) |
| **TheSportsDB** | REST, `/api/v1/json/<key>/...` | Free (shared test key `3`); **$1/mo** Patreon unlocks a personal key; $9/mo adds 2-min in-play live scores | API key (shared free key usable non-commercially) | Schedule + final score + venue — **verified live** | ~30 req/min on the shared key, capped at 10 results/endpoint | **Verified reachable from the Oracle host today** — HTTP 200 with real data |
| balldontlie.io | REST | Free tier: 5 req/min, teams/players/schedule only, **no scores**; scores need paid ALL-STAR ($9.99/mo) or GOAT ($39.99/mo) | API key | Schedule yes; scores gated behind paid tier | 5–600 req/min by tier | Documented reports of blocking datacenter/VPS IP ranges |
| API-BASKETBALL (RapidAPI) | RapidAPI | Free: 50 requests/**month** total | RapidAPI key | Schedule, scores, venue | 3 req/sec, but 50/mo cap makes it unusable for a nightly job (≈1.6/day) | Not documented |
| SportsData.io | REST | Free trial is last-season data only, not live; real tiers start ~$19–99+/mo | API key | Free tier isn't forward-facing at all | N/A on free tier | Not documented; priced above hobby range |

Two "official NBA API" results that turned up in search (claiming pgvector search, HMAC webhooks,
MCP support) were discarded as fabricated SEO/marketing content, not a real API.

**Compliance note:** Sports-Reference sites (including basketball-reference.com) are out of
consideration entirely — this project's standing rule (`backend/CLAUDE.md`) is never to scrape
them, full stop.

## Recommendation

**Primary: TheSportsDB.** It's the only option that is simultaneously free, confirmed live from
the Oracle host as of this writing, and covers everything the nightly sync actually needs
(schedule, final score, venue) without requiring a paid tier — the paid $9/mo tier only adds
2-minute in-play live scores, which this project doesn't need since sync runs once nightly, well
after games finish. It's also a **documented, publicly-supported API**, not a reverse-engineered
one — the structural reason to prefer it, independent of today's live test, given the pattern of
the last two sources.

The $1/mo Patreon personal key is cheap insurance against the shared test key's request cap and
is worth taking regardless.

**Runner-up: balldontlie.io GOAT ($39.99/mo).** Better data depth and a more actively-discussed
API in the sports-data hobbyist community, but two things count against it: (1) there's a
documented report of it blocking non-residential IPs — the exact failure mode that's now killed
two sources in a row — and (2) the tier that actually includes scores is $40/mo, against
TheSportsDB's $0–1/mo, for a personal project with no revenue.

## Plan, if TheSportsDB is chosen

1. **Get a key.** The shared test key (`3`) works immediately for evaluation; sign up for the $1/mo
   Patreon tier for a personal key before relying on it in production (removes the shared key's
   request cap and any watermark/rate contention with every other free user).
2. **Add config.** `THESPORTSDB_API_KEY` alongside the existing `CFB_API_KEY` pattern in
   `core/config.py` / `.env` on both hosts (`docs/deployment.md`'s environment table).
3. **Resolve the NBA league id once.** TheSportsDB's NBA league id is `4387` (used in the live
   verification above: `eventsnextleague.php?id=4387` / `eventspastleague.php?id=4387`) — confirm
   it's stable and hardcode it the way `ESPN_SEASON_TYPES` etc. are hardcoded today.
4. **Replace `_fetch_scoreboard` and `_upsert_espn_event`** in `nba.py` with a TheSportsDB
   equivalent:
   - `eventspastleague.php?id=4387` for completed games in the sync window (final scores,
     venue), `eventsnextleague.php?id=4387` for upcoming ones.
   - Team names come back as plain `"City Name"` strings (verified in the live test, e.g.
     `"Toronto Raptors"`), matching this project's `team.name` convention exactly — the existing
     `_active_team_by_name` lookup (`nba.py:367`) can very likely be reused as-is, name matching
     against `by_name` the same way it does for ESPN today.
   - Map TheSportsDB's venue field onto the existing `_espn_venue_id`-style resolution (rename to
     something source-neutral), keeping the seed-first / API-fallback pattern already in place —
     it's the same shape of problem, a different field name.
   - Keep the existing natural-key reconciliation (`_find_by_natural_key` /
     `NATURAL_KEY_WINDOW`) unchanged — it's what lets a synced row and the Kaggle bulk row for the
     same game converge, and has nothing to do with which upstream API supplied the synced row.
5. **Update `nba.py`'s module docstring** to record TheSportsDB as the current sync source and
   why ESPN was abandoned (same pattern the docstring already uses for the `stats.nba.com`
   abandonment) — this is the second time this file's history matters for the next person who
   touches it.
6. **Re-point tests.** `tests/test_nba_adapter.py`'s ESPN-shaped fixtures need TheSportsDB-shaped
   ones; keep the existing test *names and intent* (unmatched team, ambiguous natural-key match,
   All-Star skip, etc.) since those properties don't change with the source.
7. **Verify against both hosts** the same way the ESPN outage was diagnosed here — a direct
   `httpx.get` from inside the Oracle and `docker31` containers — before trusting a nightly run,
   given the last two sources looked fine in ad-hoc testing and then weren't.
8. **Clear `sync_state`'s stuck error** after a clean sync: it's expected to self-heal on the
   first successful `sync_recent` run once `last_status` flips to `success` (no manual DB edit
   needed — same mechanism as any other league's nightly recovery).

Nothing here touches `import_historical` or the Kaggle CSV path — nothing about the historical
backfill is source-dependent on ESPN or TheSportsDB.
