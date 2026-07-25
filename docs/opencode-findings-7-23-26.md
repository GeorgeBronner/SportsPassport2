# SportsPassport2 — Code Review Findings
**Date:** 2026-07-23
**Reviewed & actioned:** 2026-07-23 on branch `opencode-fixes-7-23`

## Summary

| Severity | Count | Fixed | Won't fix | Invalid |
|----------|-------|-------|-----------|---------|
| Critical | 3     | 3     | 0         | 0       |
| High     | 6     | 5     | 0         | 1       |
| Medium   | 9     | 6     | 2         | 1       |
| Low      | 7     | 3     | 3         | 1       |

Backend suite after the fixes: **205 passed** (was 189 — 16 new tests). Frontend
`tsc --noEmit` and `npm run build` both clean. The attendance migration was
verified end-to-end against a real SQLite file (dedupe → constraint → downgrade).

---

## Critical

### C-1: CORS wildcard with credentials enabled — ✅ FIXED
- **File:** `backend/sports_passport/main.py:66-70`
- **Issue:** `allow_origins=["*"]` with `allow_credentials=True` is a known insecure combination. Browsers will send auth cookies and JWT headers to any origin, enabling cross-origin credential theft if the app is compromised.
- **Fix applied:** Origins now come from a `CORS_ORIGINS` setting (`core/config.py`), defaulting to the Vite dev server only. The SPA is served by this same app in production, so no cross-origin entry is needed there. Documented in `.env.example`; `tests/test_app.py::TestCorsConfig` asserts `"*"` never creeps back in.

### C-2: No rate limiting on login endpoint — ✅ FIXED
- **File:** `backend/sports_passport/routers/auth.py:45-64`
- **Issue:** `POST /api/auth/login` has no rate limiting, so every registered account is open to unthrottled password guessing.
- **Fix applied:** `@limiter.limit("10/minute")` on login. The limiter's storage is process-wide, which would have made the suite's many logins fail unrelated tests, so it gained a `RATE_LIMIT_ENABLED` setting that `conftest.py` turns off; `TestLoginRateLimit` re-enables it and asserts a 429 appears.
- **Not done:** account lockout after repeated failures. Per-IP throttling is the right first control for a family app; lockout adds a denial-of-service vector against a known email.

### C-3: No database-level unique constraint on (user_id, game_id) — ✅ FIXED
- **File:** `backend/sports_passport/models/attendance.py:10-12`
- **Issue:** The application-level check in `routers/attendance.py` is check-then-insert; two concurrent requests can both pass it.
- **Fix applied:** Unique index `uq_user_game_attendance` on the model plus migration `f3a9d4b6c281`, which collapses any pre-existing duplicates (keeping the oldest row and its notes) before creating it. Two follow-on defects surfaced and were fixed with it:
  - the single-game endpoint now catches `IntegrityError` and returns the same 400 as the pre-check, instead of a 500 on the lost race;
  - `/attendance/bulk` now skips a game listed twice *within one payload* — the session doesn't autoflush, so that case never hit the existing-row query and would have violated the new index at commit.

---

## High

### H-1: Password reset returns success even when the email fails — ✅ FIXED (partially)
- **File:** `backend/sports_passport/routers/password_reset.py:82-90`
- **Issue:** On send failure the token is rolled back but the caller still gets "a reset link has been sent". The error only reaches the server log.
- **Fix applied:** The failure is now reported to Sentry alongside the log line, so it reaches an admin.
- **Deliberately unchanged:** the response text. Any user-visible distinction between "sent" and "failed" is exactly the enumeration oracle the generic message exists to prevent, and a retry loop inside the request would hold the connection open for a mail server that is already failing.

### H-2: Registration accepts passwords exceeding bcrypt's 72-byte limit — ✅ FIXED
- **File:** `backend/sports_passport/routers/auth.py:18-42`
- **Issue:** bcrypt truncates at 72 bytes, so a longer password stored at registration is not the password the user typed — and `/reset-password`, which enforces the limit, would then reject it.
- **Fix applied:** Validation moved to one `validate_password()` in `core/security.py` and used by all three paths (register, change, reset). Register previously had **no minimum length at all** either — a one-character password was accepted; it now enforces the same 8-character floor as the others. Covered by `TestPasswordValidation`.

### H-3: CFB `sync_recent` re-imports the entire season — ✅ FIXED (as recommended: logging only)
- **File:** `backend/sports_passport/services/adapters/cfb.py:175-178`
- **Issue:** CFBD's `/games` filters by year + seasonType only, never by date, so a nightly sync re-fetches ~800 games.
- **Fix applied:** `sync_recent` logs that it is doing a full-season re-sync and why. The upserts are idempotent, so this is wasteful rather than wrong, and the API gives no way to narrow it.

### H-4: Empty team filter causes invalid SQL `IN ()` — ❌ INVALID
- **File:** `backend/sports_passport/routers/games.py:66-73`
- **Verified false.** SQLAlchemy renders an empty `in_([])` as an always-false expression, not literal `IN ()`. Confirmed directly: `Game.home_team_id.in_([])` returns `[]` on SQLite with no error. There is no 500 to fix, and the endpoint already returns an empty list for an unmatched team name.

### H-5: HTTP client not pooled in adapters — ✅ FIXED
- **File:** all adapters (`nhl.py`, `cfb.py`, `cbb.py`, `nfl.py`, `mlb.py`, `nba.py`)
- **Issue:** Every request built and tore down its own `httpx.AsyncClient`, paying a fresh TCP+TLS handshake — thousands of times during a historical backfill.
- **Fix applied:** `LeagueAdapter` gained a lazily-created pooled `http` client (`http_client_kwargs` per adapter for redirects / anti-bot headers) and an `aclose()`. Lazy creation matters: the NBA adapter's historical import reads a local CSV and never opens one. The three call sites — both admin import endpoints and the scheduler's per-league sync — close it in a `finally`, so nothing leaks on the error or timeout paths.

### H-6: No request body size limits on bulk endpoints — ✅ FIXED (narrower than proposed)
- **File:** `backend/sports_passport/schemas/attendance.py`
- **Fix applied:** `BulkAttendanceRequest.games` is capped at 5000 items, rejected during parsing with a 422 rather than becoming an unbounded row-by-row loop.
- **Why not the proposed middleware:** a global body-size middleware in ASGI has to buffer or stream-count every request to enforce it, and the deployment already sits behind nginx, whose `client_max_body_size` does this properly at the edge. The schema cap fixes the actual unbounded endpoint without that.

---

## Medium

### M-1: Health check does not verify database connectivity — ✅ FIXED
- **File:** `backend/sports_passport/main.py:83-86`
- **Fix applied:** `/health` runs `SELECT 1` and returns 503 when it fails. Docker restarts the container on repeated failures, so "up but can't reach the database" must not report healthy. Covered in `tests/test_app.py`.
- **Not done:** separate `/health/live` and `/health/ready`. One container, one dependency — the split would add endpoints with no consumer.

### M-2: Admin historical import has no season range validation — ✅ FIXED
- **File:** `backend/sports_passport/routers/admin.py:55-77`
- **Fix applied:** Seasons must fall between 1850 (below MLB's 1871 Retrosheet floor) and next year. Bounding the window is strictly better than the suggested span cap: `1900-2100` is 200 seasons *and* mostly nonexistent, while a legitimate NHL backfill is 1917-present, ~110.

### M-3: SPA catch-all serves index.html for invalid API paths — ✅ FIXED
- **File:** `backend/sports_passport/main.py:105-116`
- **Fix applied:** The catch-all 404s anything under `api/` instead of returning the SPA shell with a 200.

### M-4: NBA adapter reads local CSV without existence check — ✅ FIXED
- **File:** `backend/sports_passport/services/adapters/nba.py:101-104`
- **Fix applied:** Raises a `FileNotFoundError` naming the expected path and the Kaggle dataset to download.

### M-5: No database backup strategy — ⏭️ NOT ADDRESSED (out of scope for this branch)
- **File:** `docker-compose.yml:11-12`
- **Real, and still open.** It's a host-level operational task (a cron job copying the `.db` off-box), not a code change, and it needs a decision about *where* backups go that this branch can't make. Worth doing — note that SQLite in WAL mode needs `sqlite3 .backup` or a checkpoint, not a bare `cp` of the `.db` file.

### M-6: `_attended_counts` double-counts teams on both sides — ❌ INVALID (as a correctness claim)
- **File:** `backend/sports_passport/routers/teams.py:24-38`
- The finding concedes this in its own parenthetical: a team cannot be both home and away in one game, so nothing double-counts. What remains is two queries where one conditional aggregate would do — over a search result pool capped at 300 teams, on a personal-scale SQLite database. Not worth the churn.

### M-7: Frontend uses `window.location.href` instead of React Router — ⏭️ WON'T FIX
- **File:** `frontend/src/api/client.ts:40`
- This fires only in the 401 interceptor, i.e. when the token is gone and every piece of in-memory state belongs to a session that no longer exists. Dropping that state is the point, not a side effect; a hard reload also guarantees no stale authenticated component keeps rendering. Routing it through React Router would need a navigation ref wired from outside the component tree — more machinery, worse guarantee.

### M-8: No API request timeouts in frontend — ✅ FIXED
- **File:** `frontend/src/api/client.ts:4-9`
- **Fix applied:** 30s default on the axios instance, with a 10-minute override for the three admin import/sync calls that legitimately run for minutes.

### M-9: Frontend error handlers swallow errors silently — ✅ FIXED
- **File:** `frontend/src/pages/Find.tsx:31`, `TeamDetail.tsx:94`
- **Fix applied:** Every `.catch(() => {})` and every catch that only set state now logs the error first (`Find`, `TeamDetail` ×3, `Statistics`, `MyGames`).

---

## Low

### L-1: `access_token` stored in localStorage — ⏭️ WON'T FIX (accepted risk)
- Migrating to httpOnly cookies means CSRF protection, a refresh-token flow, and reworking the axios interceptor. The finding itself rates it low priority for a personal/family app; the effort is better spent elsewhere until the threat model changes.

### L-2: No ErrorBoundary in React app — ✅ FIXED
- **Fix applied:** `components/common/ErrorBoundary.tsx` wraps `<Routes>`, showing the error message and a reload button (styled with the app's own `page`/`panel`/`ink` tokens) instead of a white screen.

### L-3: Reset endpoint doesn't differentiate token states — ⏭️ WON'T FIX
- Distinguishing "already used" from "expired" from "invalid" turns the endpoint into an oracle for whether a given token ever existed. The usability gain is a slightly better error string; the cost is leaking token state to anyone guessing.

### L-4: `create_all()` at module level masks migration issues — ❌ INVALID FOR THIS REPO (and it exposed a real bug)
- **File:** `backend/sports_passport/main.py:37`
- The premise — "after Alembic migrations have run, this is redundant" — is wrong here. **The initial migration `9182bb4bc1d2` is an empty `pass` stub.** The schema has only ever been created by `create_all()`; the later migrations are `ALTER TABLE`s layered on top of it. Removing `create_all()` would leave a fresh deployment with no tables at all.
- **Genuine bug this uncovered (not in the original findings):** on a *fresh* database, `alembic upgrade head` — which the Dockerfile runs before uvicorn starts — fails at migration `b4c9e1f7a2d3` with `no such table: teams`, because migration 1 creates nothing. Reproduced against an empty SQLite file. The existing deployment is unaffected (its schema and alembic version are already in place), so this is not urgent, but a rebuild onto an empty volume will not come up. Fixing it properly means backfilling the initial migration with the real `create_table` calls and stamping existing databases — a self-contained change, deliberately left out of this branch so it isn't buried in a 36-file diff.

### L-5: `alembic.ini` has hardcoded SQLite path — ✅ FIXED
- **Fix applied:** The `sqlalchemy.url` line is commented out with a note that `env.py` supplies it from `DATABASE_URL`. Verified `alembic current` still resolves the right database.

### L-6: Team search `ilike` not protected against wildcard patterns — ✅ FIXED
- **File:** `backend/sports_passport/routers/teams.py`, `games.py`
- **Fix applied:** New `core/queries.py::contains_pattern()` escapes `%`, `_` and the escape character itself, paired with `escape=` on every `ilike`. Searching `Ohi_` now finds a team literally named that, not "Ohio State". Covered by unit tests and endpoint tests.

### L-7: Dockerfile uses `pip install uv` — ⏭️ WON'T FIX
- `pip install uv` installs the same binary from the same maintainer and is one cache-friendly layer. The curl-pipe-sh installer adds a network fetch that isn't Docker-cached and a `PATH` fixup, in exchange for a couple of seconds on a build that runs rarely. No reliability argument survives inspection.

---

## Follow-ups worth scheduling

1. **Fresh-database migration chain is broken** (see L-4) — backfill migration `9182bb4bc1d2` with the real schema, stamp existing deployments. Blocks any rebuild onto an empty volume.
2. **Database backups** (M-5) — decide a destination, then a cron job using `sqlite3 .backup` (WAL-safe).
