"""
Tests for teams endpoints.
"""
import pytest


class TestListTeams:
    """Tests for GET /api/teams/ endpoint."""

    def test_list_all_teams(self, client, sample_teams, auth_headers):
        """Test listing all teams."""
        response = client.get("/api/teams/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("school" in team for team in data)
        assert all("id" in team for team in data)
        # Verify alphabetical ordering by school name
        schools = [team["school"] for team in data]
        assert schools == sorted(schools)

    def test_list_teams_search(self, client, sample_teams, auth_headers):
        """Test searching teams by name."""
        response = client.get(
            "/api/teams/?search=Michigan",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["school"] == "Michigan"

    def test_list_teams_filter_by_conference(self, client, sample_teams, auth_headers):
        """Test filtering teams by conference."""
        response = client.get(
            "/api/teams/?conference=Big Ten",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(team["conference"] == "Big Ten" for team in data)

    def test_list_teams_pagination(self, client, sample_teams, auth_headers):
        """Test teams pagination."""
        response = client.get(
            "/api/teams/?limit=2",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_teams_requires_auth(self, client, sample_teams):
        """Test that listing teams requires authentication."""
        response = client.get("/api/teams/")
        assert response.status_code == 401

    def test_list_teams_empty_database(self, client, auth_headers):
        """Test listing teams when database is empty."""
        response = client.get("/api/teams/", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_team_response_fields(self, client, sample_teams, auth_headers):
        """Test that team response contains all expected fields."""
        response = client.get("/api/teams/", headers=auth_headers)
        assert response.status_code == 200
        team = response.json()[0]
        assert "id" in team
        assert "school" in team
        assert "mascot" in team
        assert "abbreviation" in team
        assert "conference" in team
        assert "division" in team
        assert "api_team_id" in team
