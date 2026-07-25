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
        assert all("name" in team for team in data)
        assert all("id" in team for team in data)
        # Verify alphabetical ordering by school name
        schools = [team["name"] for team in data]
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
        assert data[0]["name"] == "Michigan"

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
        assert "name" in team
        assert "nickname" in team
        assert "abbreviation" in team
        assert "conference" in team
        assert "division" in team
        assert "league_id" in team

    def test_list_teams_filter_by_franchise_id(self, client, db_session, nhl_league, auth_headers):
        """Test filtering teams by franchise_id groups relocated identities."""
        from sports_passport.models.team import Team

        seattle = Team(
            league_id=nhl_league.id, source="nhl", source_team_id="SEA-OLD",
            name="Seattle Metropolitans", franchise_id=100, first_season=1917, last_season=1924,
        )
        relocated = Team(
            league_id=nhl_league.id, source="nhl", source_team_id="NEW",
            name="New Franchise", franchise_id=100, first_season=1925,
        )
        unrelated = Team(
            league_id=nhl_league.id, source="nhl", source_team_id="OTHER",
            name="Other Team", franchise_id=200,
        )
        db_session.add_all([seattle, relocated, unrelated])
        db_session.commit()

        response = client.get("/api/teams/?franchise_id=100", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert {t["name"] for t in data} == {"Seattle Metropolitans", "New Franchise"}


class TestGetTeam:
    """Tests for GET /api/teams/{team_id} endpoint."""

    def test_get_team(self, client, sample_teams, auth_headers):
        team_id = sample_teams[0].id
        response = client.get(f"/api/teams/{team_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == team_id
        assert data["name"] == sample_teams[0].name

    def test_get_team_not_found(self, client, auth_headers):
        response = client.get("/api/teams/999999", headers=auth_headers)
        assert response.status_code == 404

    def test_get_team_requires_auth(self, client, sample_teams):
        team_id = sample_teams[0].id
        response = client.get(f"/api/teams/{team_id}")
        assert response.status_code == 401


class TestSearchWildcards:
    """`%` and `_` are LIKE wildcards; a search for them is a literal search."""

    def test_percent_does_not_match_everything(self, client, sample_teams, auth_headers):
        response = client.get("/api/teams/?search=%25", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_underscore_does_not_match_any_character(self, client, sample_teams, auth_headers):
        # "Ohio State" would match "%Ohi_%" if the underscore stayed a wildcard
        response = client.get("/api/teams/?search=Ohi_", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
