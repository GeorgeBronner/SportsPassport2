---
name: sentry-triage
description: Review, triage, and fix errors reported to Sentry for SportsPassport2 using the `sentry` CLI. Use when asked to check Sentry, look at production errors, investigate crash reports, find out why the nightly sync failed, or resolve/archive Sentry issues.
---

# Sentry triage for SportsPassport2

The backend reports via `sentry_sdk` (`sports_passport/main.py`, gated on `SENTRY_DSN`).

**Always pass the full slug: `bronner/sportspassport2-backend`.** The `bronner` org also
holds `cfb`, `golfmapper3`, and `poker`; without it the CLI guesses from the working
directory and can pick the wrong one.

## Commands

```bash
sentry auth status                                                    # do this first
sentry issue list bronner/sportspassport2-backend --query "is:unresolved environment:prod" -t 90d
sentry issue view <SHORT_ID> --spans no
sentry issue explain <SHORT_ID>          # Seer AI — a hypothesis, verify against code
```

If auth fails, stop and ask the user to run `! sentry auth login` — it's interactive.
Don't attempt it for them.

Queries are implicit-AND with **no `OR`**. Short IDs abbreviate — the bold suffix from
the list output works alone.

**`environment:prod` is in the default query on purpose.** Dev and prod share one DSN,
so local runs land in the same project; the filter hides them rather than removing
them. Drop it (`--query "is:unresolved"`) when investigating something the user saw
locally, or when a reported error doesn't show up in the filtered list.

**Two output gotchas, both hit in practice:**
- `--json --fields ...` returns empty objects (`[{},{},{}]`) on `issue list`, but works
  on `issue view`. Use plain `--json` or the table for lists.
- `issue view` attaches hundreds of SQLAlchemy breadcrumbs on any nightly-sync failure.
  Always `--spans no`; if still too large, use
  `--json --fields shortId,title,culprit,count,firstSeen,lastSeen,level,isUnhandled,permalink`.

## Triage rules for this codebase

**Check the `environment` tag first**, whenever the default filter is off. `prod` is
the deployed container. `dev` (older events say `development`) is the user's machine,
`server_name: Marvin` — often ad-hoc throwaway scripts, not repo code. Confirm the file
in the stack trace is tracked in git before investigating; if it isn't, there's nothing
to fix.

**"Handled" does not mean harmless.** `run_sync_for_league` (`services/scheduler.py`)
wraps each league in a broad `except Exception` + `logger.exception`, deliberately, so
one league can't derail the nightly job. Adapter failures therefore arrive as
`handled: yes`, `mechanism: logging`, logger `...services.scheduler` — while a whole
league silently imported nothing. Weigh by event count and nightly repetition instead.

**Culprit maps straight to source:** `...services.adapters.nfl in _upsert_row` →
`backend/sports_passport/services/adapters/nfl.py`. One adapter per league; registry in
`adapters/__init__.py`.

**Events near 01:00 are the nightly sync.** Repeating nightly = a real adapter bug.
A single isolated one is usually an upstream blip.

**Transient upstream errors are noise.** A one-off `ConnectError`/`ReadTimeout` from
CBB, CFB, MLB, NBA, or MLS means the third-party API was briefly unreachable; the
scheduler already recorded it on `SyncState` and moved on. Archive rather than fix,
unless it recurs.

**`FileNotFoundError: 'data/seed/*.csv'`** means something reads a committed seed CSV
relative to `settings.data_dir` (the Docker bind-mount, which shadows the image's copy)
instead of from the package via `__file__`. See `venue_seed.py`'s docstring and
`tests/test_venue_seed.py`. Bulk `raw/` files are the opposite case and *do* belong on
the volume.

## Before writing a fix

This project has already hit an issue that was open in Sentry but fixed in the repo
hours after its last event. Check first:

```bash
git log --format="%H %ci %s" -- <file from the stack trace>
```

If the fix postdates **Last seen**, the work is a deploy and a resolve, not new code.
The event's `Release` tag tells you what prod is actually running.

Regression cover should pin the property that broke, not the happy path —
`tests/test_venue_seed.py` is the model (the adapter tests passed while prod was broken
because pytest's CWD made the bad relative path resolve).

## Closing

```bash
sentry issue resolve <ID>              # also: -i @commit | @next
sentry issue archive <ID> -u forever   # not a bug; -u 10x to ignore unless it recurs
```

**Confirm with the user before resolving or archiving** — it's state change visible
outside this repo — and report what you closed. Resolved issues re-open if the same
fingerprint fires again, which makes resolving a fixed-but-undeployed issue a useful
deploy check.
