"""In-process nightly sync scheduler (APScheduler).

One cron job runs each night at ``settings.sync_hour`` (server-local). It walks
every league whose ``SyncState.enabled`` is true and calls the adapter's
``sync_recent`` over an adaptive window (see ``compute_since``), recording the
outcome back onto the ``SyncState`` row so the admin UI can show last-run status.

Out-of-season leagues need no special handling: every adapter's ``sync_recent``
queries by date range, so an out-of-season window simply returns zero games.

The scheduler is started/stopped from the FastAPI lifespan and is guarded by
``settings.scheduler_enabled`` (set false in tests and one-off scripts).
"""
import asyncio
import logging
from datetime import date, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sports_passport.core.config import settings
from sports_passport.db.database import SessionLocal
from sports_passport.models.league import League
from sports_passport.models.sync_state import SyncState
from sports_passport.services.adapters import ADAPTERS, get_adapter
from sports_passport.services.adapters.base import ImportResult

logger = logging.getLogger(__name__)

# A single league's sync should never hang the whole nightly job (these are
# all third-party endpoints that can stall) — cap each league's run.
PER_LEAGUE_TIMEOUT_SECONDS = 600

_scheduler: AsyncIOScheduler | None = None

# Single-owner guard for the admin "run now" background job (see trigger_sync_all).
_sync_all_in_progress = False


def get_or_create_sync_state(db: Session, league: League) -> SyncState:
    """Return the league's SyncState row, creating a default (enabled) one if absent.

    Concurrency-safe: the scheduler and admin endpoints can both race to create
    the first row for a league. If a concurrent insert wins first, recover from
    the unique-constraint violation instead of raising.
    """
    state = db.query(SyncState).filter(SyncState.league_id == league.id).first()
    if state is not None:
        return state
    state = SyncState(league_id=league.id, enabled=True)
    db.add(state)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent caller inserted the row between our lookup and this
        # commit. league_id is unique, so it is there now — .one() rather than
        # .first() so a genuinely missing row raises instead of returning None
        # to a caller whose signature promises a SyncState.
        db.rollback()
        state = db.query(SyncState).filter(SyncState.league_id == league.id).one()
    else:
        db.refresh(state)
    return state


def compute_since(state: SyncState, today: date, lookback_days: int) -> date:
    """Adaptive lookback window.

    - Never successfully synced, or last success was today/yesterday → go back
      ``lookback_days``.
    - Otherwise (a run was missed, or the last attempt failed) → cover the whole
      gap plus a two-day cushion, so a long outage — or a failed recovery run —
      still backfills everything since the last *successful* run.
    """
    if state.last_success_at is None:
        return today - timedelta(days=lookback_days)
    days_since = (today - state.last_success_at.date()).days
    if days_since <= 1:
        return today - timedelta(days=lookback_days)
    return state.last_success_at.date() - timedelta(days=2)


async def run_sync_for_league(
    db: Session,
    league_code: str,
    since: date | None = None,
) -> ImportResult:
    """Sync one league and record the outcome on its SyncState row.

    Shared by the nightly job and the admin endpoints so every sync path
    updates the same last-run record. ``since`` overrides the adaptive window
    (used by the manual "sync last N days" admin action). Never raises — a hard
    adapter failure is captured into the returned ImportResult's ``errors`` and
    onto the SyncState — so the nightly loop can't be derailed by one league.
    """
    league = db.query(League).filter(League.code == league_code.upper()).first()
    if league is None:
        raise KeyError(f"Unknown league: {league_code}")

    state = get_or_create_sync_state(db, league)
    window_start = (
        since
        if since is not None
        else compute_since(state, date.today(), settings.sync_lookback_days)
    )

    state.last_status = "running"
    db.commit()

    result = ImportResult(league=league.code)
    started = datetime.now()
    adapter = None
    try:
        adapter = get_adapter(league_code, db)
        result = await asyncio.wait_for(
            adapter.sync_recent(since=window_start),
            timeout=PER_LEAGUE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        db.rollback()  # discard any partial work left by the cancelled coroutine
        result.errors.append(f"timed out after {PER_LEAGUE_TIMEOUT_SECONDS}s")
        logger.warning("Sync for %s timed out", league_code)
    except Exception as e:  # noqa: BLE001 — record any adapter failure, don't crash the job
        # A failed flush/commit inside the adapter can leave the session in a
        # state that must be rolled back before it can be used again — without
        # this, the finally block's db.commit() below would itself raise.
        db.rollback()
        result.errors.append(str(e))
        logger.exception("Sync for %s failed", league_code)
    finally:
        if adapter is not None:
            await adapter.aclose()  # release the adapter's pooled connections
        state.last_run_at = started
        state.last_duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        state.last_games_imported = result.games_imported
        state.last_games_updated = result.games_updated
        state.last_error = result.errors[0] if result.errors else None
        state.last_status = "error" if result.errors else "success"
        if not result.errors:
            state.last_success_at = started
        db.commit()

    return result


async def sync_all_enabled(db: Session) -> list[ImportResult]:
    """Run the nightly sync over every enabled, adapter-backed league.

    Used by both the scheduler (via ``run_nightly_sync``) and the admin
    "run now" endpoint, so on-demand runs behave exactly like the nightly one
    (adaptive window, enabled-only).
    """
    results: list[ImportResult] = []
    for league in db.query(League).order_by(League.code).all():
        if league.code not in ADAPTERS:
            continue
        state = get_or_create_sync_state(db, league)
        if not state.enabled:
            logger.info("Skipping %s (auto-sync disabled)", league.code)
            continue
        results.append(await run_sync_for_league(db, league.code))
    return results


def sync_all_running() -> bool:
    """True if the admin "run now" background job is currently in flight."""
    return _sync_all_in_progress


def start_sync_all() -> bool:
    """Reserve the single-owner slot for a background sync-all run.

    Returns False (and reserves nothing) if one is already running, so callers
    can't kick off two overlapping full syncs.
    """
    global _sync_all_in_progress
    if _sync_all_in_progress:
        return False
    _sync_all_in_progress = True
    return True


async def run_sync_all_background() -> None:
    """Background entry point for the admin "run now" endpoint.

    Runs after the HTTP response is already sent (via FastAPI BackgroundTasks),
    so the request can't be held open for the ~hour a full multi-league sync
    may take. Uses its own DB session — the request's session is closed once
    the response is sent — and releases the slot reserved by start_sync_all().
    """
    global _sync_all_in_progress
    db = SessionLocal()
    try:
        await sync_all_enabled(db)
    finally:
        db.close()
        _sync_all_in_progress = False


async def run_nightly_sync() -> None:
    """Scheduler entry point. Uses its own DB session (not request-scoped)."""
    logger.info("Nightly sync starting")
    db = SessionLocal()
    try:
        await sync_all_enabled(db)
    finally:
        db.close()
    logger.info("Nightly sync finished")


def start_scheduler() -> None:
    """Start the nightly cron job. No-op if disabled or already running."""
    global _scheduler
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=false) — nightly sync not started")
        return
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_nightly_sync,
        trigger=CronTrigger(hour=settings.sync_hour, minute=0),
        id="nightly_sync",
        replace_existing=True,
        misfire_grace_time=3600,   # if the app was down at the trigger, still run within the hour
        coalesce=True,             # collapse multiple missed runs into one
    )
    _scheduler.start()
    logger.info("Nightly sync scheduled for %02d:00 server-local", settings.sync_hour)


def shutdown_scheduler() -> None:
    """Stop the scheduler if running."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
