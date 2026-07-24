"""
Tests for authentication endpoints.
"""
import pytest


class TestUserRegistration:
    """Tests for user registration endpoint."""

    def test_register_new_user(self, client):
        """Test successful user registration."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "full_name": "New User"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert data["is_admin"] is False
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, client, test_user):
        """Test registration with existing email fails."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": test_user.email,
                "password": "password123",
                "full_name": "Duplicate User"
            }
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client):
        """Test registration with invalid email fails."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "not-an-email",
                "password": "password123",
                "full_name": "Test User"
            }
        )
        assert response.status_code == 422

    def test_register_missing_fields(self, client):
        """Test registration with missing required fields fails."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com"
            }
        )
        assert response.status_code == 422


class TestUserLogin:
    """Tests for user login endpoint."""

    def test_login_success(self, client, test_user):
        """Test successful login."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": test_user.email,
                "password": "testpassword123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    def test_login_wrong_password(self, client, test_user):
        """Test login with wrong password fails."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": test_user.email,
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user fails."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "password123"
            }
        )
        assert response.status_code == 401

    def test_login_missing_credentials(self, client):
        """Test login with missing credentials fails."""
        response = client.post(
            "/api/auth/login",
            data={}
        )
        assert response.status_code == 422


class TestCurrentUser:
    """Tests for get current user endpoint."""

    def test_get_current_user_success(self, client, test_user, auth_headers):
        """Test getting current user info with valid token."""
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["full_name"] == test_user.full_name
        assert data["is_admin"] == test_user.is_admin
        assert "password" not in data
        assert "hashed_password" not in data

    def test_get_current_user_no_token(self, client):
        """Test getting current user without token fails."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token fails."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_admin_user_has_admin_flag(self, client, test_admin, admin_headers):
        """Test that admin user has is_admin=True."""
        response = client.get("/api/auth/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["is_admin"] is True


class TestPasswordValidation:
    """Register enforces the same password rules as change/reset."""

    def test_register_rejects_short_password(self, client):
        response = client.post(
            "/api/auth/register",
            json={"email": "short@example.com", "password": "abc123", "full_name": "Short"},
        )
        assert response.status_code == 422

    def test_register_rejects_password_over_bcrypt_limit(self, client):
        """bcrypt truncates past 72 bytes; storing a silently-truncated hash
        would leave the user with a password the reset flow refuses."""
        response = client.post(
            "/api/auth/register",
            json={"email": "long@example.com", "password": "a" * 73, "full_name": "Long"},
        )
        assert response.status_code == 422

    def test_register_accepts_password_at_limit(self, client):
        response = client.post(
            "/api/auth/register",
            json={"email": "limit@example.com", "password": "a" * 72, "full_name": "Limit"},
        )
        assert response.status_code == 201


class TestLoginRateLimit:
    """The limiter is disabled suite-wide (see conftest); switch it on here."""

    def test_login_is_rate_limited(self, client, test_user):
        from sports_passport.core.limiter import limiter

        limiter.enabled = True
        limiter.reset()
        try:
            statuses = [
                client.post(
                    "/api/auth/login",
                    data={"username": test_user.email, "password": "wrongpassword"},
                ).status_code
                for _ in range(12)
            ]
        finally:
            limiter.reset()
            limiter.enabled = False

        assert statuses[0] == 401
        assert 429 in statuses, "brute-force attempts should be throttled"
