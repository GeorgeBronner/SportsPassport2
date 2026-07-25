"""
Tests for the nightly sync scheduler and the sync-state admin endpoints.

The scheduler itself (APScheduler) is not started in tests (conftest sets
SCHEDULER_ENABLED=false); these exercise the sync *logic* — adaptive lookback,
per-league state recording, enable/disable — with a mocked adapter.
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from sports_passport.models.sync_state import SyncState
from sports_passport.services import scheduler
from sports_passport.services.adapters.base import ImportResult
from sports_passport.services.scheduler import compute_since, run_sync_for_league, sync_all_enabled


def _mock_adapter(**overrides):
    adapter = Mock()
    result = ImportResult(league="CFB", games_imported=5, games_updated=2, **overrides)
    adapter.sync_recent = AsyncMock(return_value=result)
    adapter.aclose = AsyncMock()
    return adapter


class TestComputeSince:
    """Adaptive lookback window, keyed off the last *successful* run."""

    def test_first_run_uses_lookback(self):
        state = SyncState(last_success_at=None)
        today = date(2026, 7, 16)
        assert compute_since(state, today, lookback_days=3) == today - timedelta(days=3)

    def test_ran_yesterday_uses_lookback(self):
        state = SyncState(last_success_at=datetime(2026, 7, 15, 6, 0))
        today = date(2026, 7, 16)
        assert compute_since(state, today, lookback_days=3) == today - timedelta(days=3)

    def test_ran_today_uses_lookback(self):
        state = SyncState(last_success_at=datetime(2026, 7, 16, 6, 0))
        today = date(2026, 7, 16)
        assert compute_since(state, today, lookback_days=3) == today - timedelta(days=3)

    def test_missed_runs_covers_gap_plus_two_days(self):
        # Last succeeded 10 days ago -> go back to that date minus a 2-day cushion.
        last = datetime(2026, 7, 6, 6, 0)
        state = SyncState(last_success_at=last)
        today = date(2026, 7, 16)
        assert compute_since(state, today, lookback_days=3) == last.date() - timedelta(days=2)

    def test_failed_recovery_run_does_not_advance_checkpoint(self):
        # A run attempted today that failed must not look like a fresh success:
        # last_success_at (not last_run_at) drives the window, so the next
        # attempt still covers the whole gap back to the last real success.
        last_success = datetime(2026, 7, 6, 6, 0)
        state = SyncState(last_success_at=last_success, last_run_at=datetime(2026, 7, 16, 6, 0))
        today = date(2026, 7, 16)
        assert compute_since(state, today, lookback_days=3) == last_success.date() - timedelta(days=2)


class TestRunSyncForLeague:
    """run_sync_for_league records outcome on SyncState and never raises."""

    @patch('sports_passport.services.scheduler.get_adapter')
    def test_records_success(self, mock_get_adapter, client, db_session):
        # client fixture ensures the app/tables exist; db_session is the session.
        import asyncio
        mock_get_adapter.return_value = _mock_adapter()
        result = asyncio.run(
            run_sync_for_league(db_session, "CFB")
        )
        assert result.games_imported == 5
        from sports_passport.models.league import League
        league = db_session.query(League).filter(League.code == "CFB").first()
        state = db_session.query(SyncState).filter(SyncState.league_id == league.id).first()
        assert state.last_status == "success"
        assert state.last_games_imported == 5
        assert state.last_games_updated == 2
        assert state.last_run_at is not None
        assert state.last_success_at is not None
        assert state.last_error is None

    @patch('sports_passport.services.scheduler.get_adapter')
    def test_hard_failure_recorded_not_raised(self, mock_get_adapter, db_session):
        adapter = Mock()
        adapter.sync_recent = AsyncMock(side_effect=Exception("network down"))
        adapter.aclose = AsyncMock()
        mock_get_adapter.return_value = adapter
        import asyncio
        result = asyncio.run(
            run_sync_for_league(db_session, "CFB")
        )
        assert "network down" in result.errors[0]
        from sports_passport.models.league import League
        league = db_session.query(League).filter(League.code == "CFB").first()
        state = db_session.query(SyncState).filter(SyncState.league_id == league.id).first()
        assert state.last_status == "error"
        assert "network down" in state.last_error
        # A failed attempt is not a success — the adaptive-lookback checkpoint
        # must not advance, or a later outage recovery would skip the gap.
        assert state.last_success_at is None

    @patch('sports_passport.services.scheduler.get_adapter')
    def test_recovers_from_failed_flush(self, mock_get_adapter, db_session):
        """A DB error inside sync_recent must not leave the session unable to
        commit the outcome (regression: finally-block db.commit() would raise
        PendingRollbackError without a rollback() in the except branch first)."""
        async def _boom(since):
            db_session.add(SyncState(league_id=None))  # violates NOT NULL
            db_session.flush()

        adapter = Mock()
        adapter.sync_recent = AsyncMock(side_effect=_boom)
        adapter.aclose = AsyncMock()
        mock_get_adapter.return_value = adapter

        import asyncio
        result = asyncio.run(run_sync_for_league(db_session, "CFB"))

        assert result.errors  # captured, not raised
        from sports_passport.models.league import League
        league = db_session.query(League).filter(League.code == "CFB").first()
        state = db_session.query(SyncState).filter(SyncState.league_id == league.id).first()
        assert state.last_status == "error"
        assert state.last_run_at is not None

    @patch('sports_passport.services.scheduler.get_adapter')
    def test_uses_explicit_since(self, mock_get_adapter, db_session):
        adapter = _mock_adapter()
        mock_get_adapter.return_value = adapter
        import asyncio
        since = date(2026, 1, 1)
        asyncio.run(
            run_sync_for_league(db_session, "CFB", since=since)
        )
        adapter.sync_recent.assert_awaited_once_with(since=since)


class TestSyncAllEnabled:
    """sync_all_enabled honors the per-league enabled flag."""

    @patch('sports_passport.services.scheduler.get_adapter')
    def test_skips_disabled_leagues(self, mock_get_adapter, db_session):
        from sports_passport.models.league import League
        mock_get_adapter.return_value = _mock_adapter()
        # Disable everything except CFB.
        for league in db_session.query(League).all():
            db_session.add(SyncState(league_id=league.id, enabled=(league.code == "CFB")))
        db_session.commit()

        import asyncio
        results = asyncio.run(sync_all_enabled(db_session))
        assert [r.league for r in results] == ["CFB"]


class TestSyncStateEndpoints:
    """Admin sync-state endpoints and status fields."""

    def test_status_includes_sync_defaults(self, client, admin_headers):
        response = client.get("/api/admin/status", headers=admin_headers)
        assert response.status_code == 200
        cfb = next(r for r in response.json() if r["league"] == "CFB")
        assert cfb["sync_enabled"] is True          # defaults true before any row exists
        assert cfb["last_sync_at"] is None
        assert cfb["last_sync_status"] is None

    def test_toggle_sync_enabled(self, client, admin_headers):
        response = client.patch(
            "/api/admin/sync-state/CFB",
            json={"enabled": False},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json() == {"league": "CFB", "enabled": False}

        # Reflected in status
        status = client.get("/api/admin/status", headers=admin_headers).json()
        cfb = next(r for r in status if r["league"] == "CFB")
        assert cfb["sync_enabled"] is False

    def test_toggle_unknown_league_404(self, client, admin_headers):
        response = client.patch(
            "/api/admin/sync-state/XFL",
            json={"enabled": False},
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_toggle_requires_admin(self, client, auth_headers):
        response = client.patch(
            "/api/admin/sync-state/CFB",
            json={"enabled": False},
            headers=auth_headers,
        )
        assert response.status_code == 403

    @patch('sports_passport.services.scheduler.get_adapter')
    def test_sync_all_endpoint(self, mock_get_adapter, client, admin_headers):
        mock_get_adapter.return_value = _mock_adapter()
        response = client.post("/api/admin/sync-all", headers=admin_headers)
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"
        # BackgroundTasks run synchronously within the TestClient's ASGI call,
        # so by the time post() returns, every enabled league has been synced.
        status_rows = client.get("/api/admin/status", headers=admin_headers).json()
        adapter_backed = [r for r in status_rows if r["adapter_available"]]
        assert len(adapter_backed) == 6
        assert all(r["last_sync_status"] == "success" for r in adapter_backed)
        assert all(r["last_sync_games_imported"] == 5 for r in adapter_backed)

    def test_sync_all_rejects_concurrent_run(self):
        assert scheduler.start_sync_all() is True
        try:
            assert scheduler.sync_all_running() is True
            assert scheduler.start_sync_all() is False
        finally:
            scheduler._sync_all_in_progress = False

    @patch('sports_passport.services.scheduler.get_adapter')
    def test_manual_sync_records_state(self, mock_get_adapter, client, admin_headers):
        mock_get_adapter.return_value = _mock_adapter()
        client.post("/api/admin/sync/CFB", headers=admin_headers)
        status = client.get("/api/admin/status", headers=admin_headers).json()
        cfb = next(r for r in status if r["league"] == "CFB")
        assert cfb["last_sync_status"] == "success"
        assert cfb["last_sync_games_imported"] == 5
        assert cfb["last_sync_at"] is not None
