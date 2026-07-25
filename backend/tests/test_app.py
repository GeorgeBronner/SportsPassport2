"""
Tests for app-level behaviour: health check, routing fallbacks, CORS config.
"""
from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from sports_passport.core.config import settings
from sports_passport.core.queries import contains_pattern


class TestHealthCheck:
    def test_health_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_health_reports_unhealthy_when_db_unreachable(self, client):
        """Docker restarts on repeated failures, so a process that can't reach
        its database must not report itself healthy."""
        with patch("sports_passport.main.SessionLocal") as mock_session:
            mock_session.return_value.__enter__.return_value.execute.side_effect = (
                OperationalError("SELECT 1", {}, Exception("no such database"))
            )
            response = client.get("/health")
        assert response.status_code == 503


class TestApiRouting:
    def test_unknown_api_path_returns_404(self, client):
        """An unmatched /api route is a broken route, not a client-side one —
        it must not fall through to the SPA shell."""
        response = client.get("/api/definitely-not-a-route")
        assert response.status_code == 404
        assert "text/html" not in response.headers.get("content-type", "")

    def test_bare_api_path_returns_404(self, client):
        """"/api" with nothing after it is no more a client-side route than
        "/api/x" — the prefix check has to cover it too."""
        response = client.get("/api")
        assert response.status_code == 404
        assert "text/html" not in response.headers.get("content-type", "")


class TestCorsConfig:
    def test_cors_origins_are_explicit(self):
        """"*" plus allow_credentials lets any origin make credentialed calls."""
        assert "*" not in settings.cors_origin_list
        assert settings.cors_origin_list


class TestLikePattern:
    def test_wildcards_are_escaped(self):
        assert contains_pattern("100%") == "%100\\%%"
        assert contains_pattern("a_b") == "%a\\_b%"
        assert contains_pattern("back\\slash") == "%back\\\\slash%"

    def test_plain_term_unchanged(self):
        assert contains_pattern("Alabama") == "%Alabama%"
