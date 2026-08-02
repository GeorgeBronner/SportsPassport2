"""
Tests for change-password and forgot/reset-password endpoints.
"""
from datetime import UTC, datetime, timedelta

from sports_passport.models.password_reset_token import PasswordResetToken
from sports_passport.routers.password_reset import _hash_token


class TestChangePassword:
    """Tests for PUT /api/auth/password."""

    def test_change_password_success(self, client, test_user, auth_headers):
        response = client.put(
            "/api/auth/password",
            json={"current_password": "testpassword123", "new_password": "newpassword456"},
            headers=auth_headers,
        )
        assert response.status_code == 204

        # New password works, old one no longer does
        login = client.post(
            "/api/auth/login",
            data={"username": test_user.email, "password": "newpassword456"},
        )
        assert login.status_code == 200

        old_login = client.post(
            "/api/auth/login",
            data={"username": test_user.email, "password": "testpassword123"},
        )
        assert old_login.status_code == 401

    def test_change_password_wrong_current_password(self, client, auth_headers):
        response = client.put(
            "/api/auth/password",
            json={"current_password": "wrongpassword", "new_password": "newpassword456"},
            headers=auth_headers,
        )
        assert response.status_code == 401

    def test_change_password_too_short(self, client, auth_headers):
        response = client.put(
            "/api/auth/password",
            json={"current_password": "testpassword123", "new_password": "short"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_change_password_requires_auth(self, client):
        response = client.put(
            "/api/auth/password",
            json={"current_password": "testpassword123", "new_password": "newpassword456"},
        )
        assert response.status_code == 401


class TestForgotPassword:
    """Tests for POST /api/auth/forgot-password."""

    def test_forgot_password_existing_email_creates_token(self, client, test_user, db_session):
        response = client.post("/api/auth/forgot-password", json={"email": test_user.email})
        assert response.status_code == 200

        tokens = (
            db_session.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == test_user.id)
            .all()
        )
        assert len(tokens) == 1
        assert tokens[0].used is False

    def test_forgot_password_unknown_email_no_token(self, client, db_session):
        response = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
        assert response.status_code == 200
        assert db_session.query(PasswordResetToken).count() == 0

    def test_forgot_password_invalidates_previous_token(self, client, test_user, db_session):
        client.post("/api/auth/forgot-password", json={"email": test_user.email})
        client.post("/api/auth/forgot-password", json={"email": test_user.email})

        tokens = (
            db_session.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == test_user.id)
            .all()
        )
        assert len(tokens) == 1


class TestResetPassword:
    """Tests for POST /api/auth/reset-password."""

    def _create_token(self, db_session, user, *, used=False, expired=False):
        raw_token = "raw-test-token"
        expires_at = datetime.now(UTC) + (
            timedelta(minutes=-5) if expired else timedelta(minutes=15)
        )
        token = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=expires_at,
            used=used,
        )
        db_session.add(token)
        db_session.commit()
        return raw_token

    def test_reset_password_success(self, client, test_user, db_session):
        raw_token = self._create_token(db_session, test_user)

        response = client.post(
            "/api/auth/reset-password",
            json={"token": raw_token, "new_password": "brandnewpassword"},
        )
        assert response.status_code == 200

        login = client.post(
            "/api/auth/login",
            data={"username": test_user.email, "password": "brandnewpassword"},
        )
        assert login.status_code == 200

        token = db_session.query(PasswordResetToken).filter(PasswordResetToken.user_id == test_user.id).first()
        assert token.used is True

    def test_reset_password_expired_token(self, client, test_user, db_session):
        raw_token = self._create_token(db_session, test_user, expired=True)

        response = client.post(
            "/api/auth/reset-password",
            json={"token": raw_token, "new_password": "brandnewpassword"},
        )
        assert response.status_code == 400

    def test_reset_password_used_token(self, client, test_user, db_session):
        raw_token = self._create_token(db_session, test_user, used=True)

        response = client.post(
            "/api/auth/reset-password",
            json={"token": raw_token, "new_password": "brandnewpassword"},
        )
        assert response.status_code == 400

    def test_reset_password_invalid_token(self, client):
        response = client.post(
            "/api/auth/reset-password",
            json={"token": "not-a-real-token", "new_password": "brandnewpassword"},
        )
        assert response.status_code == 400

    def test_reset_password_too_short(self, client, test_user, db_session):
        raw_token = self._create_token(db_session, test_user)

        response = client.post(
            "/api/auth/reset-password",
            json={"token": raw_token, "new_password": "short"},
        )
        assert response.status_code == 422
