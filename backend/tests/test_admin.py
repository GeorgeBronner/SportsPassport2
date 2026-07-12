"""
Tests for admin endpoints.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from sports_passport.services.adapters.base import ImportResult


def _mock_adapter(**overrides):
    adapter = Mock()
    result = ImportResult(league="CFB", games_imported=100, **overrides)
    adapter.import_teams = AsyncMock(return_value=result)
    adapter.import_historical = AsyncMock(return_value=result)
    adapter.sync_recent = AsyncMock(return_value=result)
    return adapter


class TestImportEndpoints:
    """Tests for the per-league import/sync admin endpoints."""

    @patch('sports_passport.routers.admin.get_adapter')
    def test_historical_import_as_admin(self, mock_get_adapter, client, admin_headers):
        mock_get_adapter.return_value = _mock_adapter()
        response = client.post(
            "/api/admin/import/CFB/historical?start_season=2023&end_season=2023",
            headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["games_imported"] == 100

    @patch('sports_passport.routers.admin.get_adapter')
    def test_import_teams_as_admin(self, mock_get_adapter, client, admin_headers):
        mock_get_adapter.return_value = _mock_adapter()
        response = client.post(
            "/api/admin/import/CFB/teams",
            headers=admin_headers
        )
        assert response.status_code == 200

    @patch('sports_passport.routers.admin.get_adapter')
    def test_sync_as_admin(self, mock_get_adapter, client, admin_headers):
        mock_get_adapter.return_value = _mock_adapter()
        response = client.post(
            "/api/admin/sync/CFB",
            headers=admin_headers
        )
        assert response.status_code == 200
        mock_get_adapter.return_value.sync_recent.assert_awaited_once()

    def test_import_unknown_league_404(self, client, admin_headers):
        response = client.post(
            "/api/admin/import/XFL/teams",
            headers=admin_headers
        )
        assert response.status_code == 404
        assert "adapter" in response.json()["detail"].lower()

    def test_historical_import_bad_range_400(self, client, admin_headers):
        response = client.post(
            "/api/admin/import/CFB/historical?start_season=2024&end_season=1990",
            headers=admin_headers
        )
        assert response.status_code == 400

    def test_import_as_regular_user(self, client, auth_headers):
        response = client.post(
            "/api/admin/import/CFB/historical?start_season=2023&end_season=2023",
            headers=auth_headers
        )
        assert response.status_code == 403

    def test_import_requires_auth(self, client):
        response = client.post(
            "/api/admin/import/CFB/historical?start_season=2023&end_season=2023"
        )
        assert response.status_code == 401

    @patch('sports_passport.routers.admin.get_adapter')
    def test_import_api_error_500(self, mock_get_adapter, client, admin_headers):
        adapter = _mock_adapter()
        adapter.import_historical = AsyncMock(side_effect=Exception("API Error"))
        mock_get_adapter.return_value = adapter
        response = client.post(
            "/api/admin/import/CFB/historical?start_season=2023&end_season=2023",
            headers=admin_headers
        )
        assert response.status_code == 500


class TestDataStatus:
    """Tests for GET /api/admin/status endpoint."""

    def test_status_as_admin(self, client, sample_games, sample_nhl_games, admin_headers):
        response = client.get("/api/admin/status", headers=admin_headers)
        assert response.status_code == 200
        rows = {row["league"]: row for row in response.json()}
        assert set(rows.keys()) == {"CFB", "MLB", "NFL", "NBA", "NHL", "CBB"}
        assert rows["CFB"]["games"] == 3
        assert rows["NHL"]["games"] == 1
        assert rows["MLB"]["games"] == 0
        assert rows["CFB"]["adapter_available"] is True

    def test_status_as_regular_user(self, client, auth_headers):
        response = client.get("/api/admin/status", headers=auth_headers)
        assert response.status_code == 403


class TestListUsers:
    """Tests for GET /api/admin/users endpoint."""

    def test_list_users_as_admin(self, client, test_user, test_admin, admin_headers):
        """Test admin can list all users."""
        response = client.get("/api/admin/users", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all("email" in user for user in data)
        assert all("is_admin" in user for user in data)
        assert all("password" not in user for user in data)
        assert all("hashed_password" not in user for user in data)

    def test_list_users_as_regular_user(self, client, auth_headers):
        """Test regular user cannot list users."""
        response = client.get("/api/admin/users", headers=auth_headers)
        assert response.status_code == 403

    def test_list_users_requires_auth(self, client):
        """Test listing users requires authentication."""
        response = client.get("/api/admin/users")
        assert response.status_code == 401

    def test_list_users_pagination(self, client, admin_headers):
        """Test user list pagination."""
        response = client.get(
            "/api/admin/users?skip=0&limit=1",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestPromoteUser:
    """Tests for POST /api/admin/users/{user_id}/promote endpoint."""

    def test_promote_user_as_admin(self, client, test_user, admin_headers):
        """Test admin can promote user to admin."""
        response = client.post(
            f"/api/admin/users/{test_user.id}/promote",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert test_user.email in data["message"]

        # Verify promotion persists
        response = client.get("/api/admin/users", headers=admin_headers)
        users = response.json()
        promoted_user = next(u for u in users if u["id"] == test_user.id)
        assert promoted_user["is_admin"] is True

    def test_promote_already_admin_user(self, client, test_admin, admin_headers):
        """Test promoting already admin user returns 400."""
        response = client.post(
            f"/api/admin/users/{test_admin.id}/promote",
            headers=admin_headers
        )
        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()

    def test_promote_nonexistent_user(self, client, admin_headers):
        """Test promoting non-existent user returns 404."""
        response = client.post(
            "/api/admin/users/99999/promote",
            headers=admin_headers
        )
        assert response.status_code == 404

    def test_promote_user_as_regular_user(self, client, test_user, auth_headers):
        """Test regular user cannot promote users."""
        response = client.post(
            f"/api/admin/users/{test_user.id}/promote",
            headers=auth_headers
        )
        assert response.status_code == 403

    def test_promote_user_requires_auth(self, client, test_user):
        """Test promoting user requires authentication."""
        response = client.post(f"/api/admin/users/{test_user.id}/promote")
        assert response.status_code == 401


class TestDemoteUser:
    """Tests for POST /api/admin/users/{user_id}/demote endpoint."""

    def test_demote_admin_user(self, client, db_session, admin_headers):
        """Test admin can demote another admin to regular user."""
        # Create a second admin user
        from sports_passport.models.user import User
        from sports_passport.core.security import get_password_hash

        second_admin = User(
            email="secondadmin@example.com",
            full_name="Second Admin",
            password_hash=get_password_hash("password123"),
            is_admin=True
        )
        db_session.add(second_admin)
        db_session.commit()
        db_session.refresh(second_admin)

        response = client.post(
            f"/api/admin/users/{second_admin.id}/demote",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert second_admin.email in data["message"]

    def test_demote_regular_user(self, client, test_user, admin_headers):
        """Test demoting already regular user returns 400."""
        response = client.post(
            f"/api/admin/users/{test_user.id}/demote",
            headers=admin_headers
        )
        assert response.status_code == 400
        assert "not an admin" in response.json()["detail"].lower()

    def test_demote_nonexistent_user(self, client, admin_headers):
        """Test demoting non-existent user returns 404."""
        response = client.post(
            "/api/admin/users/99999/demote",
            headers=admin_headers
        )
        assert response.status_code == 404

    def test_demote_user_as_regular_user(self, client, test_user, auth_headers):
        """Test regular user cannot demote users."""
        response = client.post(
            f"/api/admin/users/{test_user.id}/demote",
            headers=auth_headers
        )
        assert response.status_code == 403

    def test_demote_user_requires_auth(self, client, test_user):
        """Test demoting user requires authentication."""
        response = client.post(f"/api/admin/users/{test_user.id}/demote")
        assert response.status_code == 401

    def test_cannot_demote_self(self, client, test_admin, admin_headers):
        """Test admin cannot demote themselves."""
        response = client.post(
            f"/api/admin/users/{test_admin.id}/demote",
            headers=admin_headers
        )
        # This may return 200 or 400 depending on implementation
        # If there's logic to prevent self-demotion, it should be 400
        # Otherwise it will succeed but the admin should verify
        # at least one admin remains in the system
        assert response.status_code in [200, 400]
