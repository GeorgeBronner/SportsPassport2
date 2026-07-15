"""
Tests for games endpoints.
"""
import pytest


class TestListGames:
    """Tests for GET /api/games/ endpoint."""

    def test_list_all_games(self, client, sample_games, auth_headers):
        """Test listing all games."""
        response = client.get("/api/games/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("id" in game for game in data)
        assert all("home_team" in game for game in data)
        assert all("away_team" in game for game in data)

    def test_list_games_filter_by_season(self, client, sample_games, auth_headers):
        """Test filtering games by season."""
        response = client.get(
            "/api/games/?season=2023",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all(game["season"] == 2023 for game in data)

    def test_list_games_filter_by_team(self, client, sample_games, auth_headers):
        """Test filtering games by team name."""
        response = client.get(
            "/api/games/?team=Alabama",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Verify Alabama is either home or away team
        for game in data:
            assert (game["home_team"]["name"] == "Alabama" or
                    game["away_team"]["name"] == "Alabama")

    def test_list_games_combined_filters(self, client, sample_games, auth_headers):
        """Test filtering games by both team and season."""
        response = client.get(
            "/api/games/?team=Michigan&season=2023",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        for game in data:
            assert game["season"] == 2023
            assert (game["home_team"]["name"] == "Michigan" or
                    game["away_team"]["name"] == "Michigan")

    def test_list_games_pagination(self, client, sample_games, auth_headers):
        """Test games pagination."""
        response = client.get(
            "/api/games/?limit=2",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_games_requires_auth(self, client, sample_games):
        """Test that listing games requires authentication."""
        response = client.get("/api/games/")
        assert response.status_code == 401


class TestGetGame:
    """Tests for GET /api/games/{game_id} endpoint."""

    def test_get_game_by_id(self, client, sample_games, auth_headers):
        """Test getting a single game by ID."""
        game_id = sample_games[0].id
        response = client.get(f"/api/games/{game_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == game_id
        assert "home_team" in data
        assert "away_team" in data
        assert "venue" in data

    def test_get_nonexistent_game(self, client, auth_headers):
        """Test getting a non-existent game returns 404."""
        response = client.get("/api/games/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_get_game_requires_auth(self, client, sample_games):
        """Test that getting a game requires authentication."""
        response = client.get(f"/api/games/{sample_games[0].id}")
        assert response.status_code == 401


class TestSearchGames:
    """Tests for GET /api/games/search/ endpoint."""

    def test_search_games_by_team(self, client, sample_games, auth_headers):
        """Test searching games by team name."""
        response = client.get(
            "/api/games/search/?q=Ohio",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        for game in data:
            assert ("Ohio State" in game["home_team"]["name"] or
                    "Ohio State" in game["away_team"]["name"])

    def test_search_games_partial_match(self, client, sample_games, auth_headers):
        """Test partial matching in game search."""
        response = client.get(
            "/api/games/search/?q=Mich",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_search_games_min_length(self, client, auth_headers):
        """Test search requires minimum query length."""
        response = client.get(
            "/api/games/search/?q=A",
            headers=auth_headers
        )
        assert response.status_code == 422

    def test_search_games_no_results(self, client, sample_games, auth_headers):
        """Test search with no matching results."""
        response = client.get(
            "/api/games/search/?q=NonexistentTeam",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json() == []


class TestListSeasons:
    """Tests for GET /api/games/seasons endpoint."""

    def test_list_seasons(self, client, sample_games, auth_headers):
        """Test listing all available seasons."""
        response = client.get("/api/games/seasons", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["season"] == 2023
        assert data[0]["game_count"] == 3

    def test_list_seasons_ordering(self, client, sample_games, auth_headers):
        """Test seasons are returned in descending order."""
        response = client.get("/api/games/seasons", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        seasons = [item["season"] for item in data]
        assert seasons == sorted(seasons, reverse=True)

    def test_list_seasons_requires_auth(self, client, sample_games):
        """Test that listing seasons requires authentication."""
        response = client.get("/api/games/seasons")
        assert response.status_code == 401

    def test_list_seasons_empty_database(self, client, auth_headers):
        """Test listing seasons when database is empty."""
        response = client.get("/api/games/seasons", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []


class TestCountGames:
    """Tests for GET /api/games/count endpoint."""

    def test_count_all_games(self, client, sample_games, auth_headers):
        """Test counting all games."""
        response = client.get("/api/games/count", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3

    def test_count_games_by_season(self, client, sample_games, auth_headers):
        """Test counting games filtered by season."""
        response = client.get(
            "/api/games/count?season=2023",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3

    def test_count_games_by_team(self, client, sample_games, auth_headers):
        """Test counting games filtered by team."""
        response = client.get(
            "/api/games/count?team=Alabama",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_count_games_combined_filters(self, client, sample_games, auth_headers):
        """Test counting games with combined filters."""
        response = client.get(
            "/api/games/count?team=Michigan&season=2023",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_count_games_no_matches(self, client, sample_games, auth_headers):
        """Test counting games with no matching results."""
        response = client.get(
            "/api/games/count?season=2025",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0


class TestListTeamGames:
    """Tests for GET /api/games/team/{team_id} endpoint."""

    def test_list_team_games(self, client, sample_games, sample_teams, auth_headers):
        """Test listing all games for a specific team."""
        # Alabama is sample_teams[0]
        alabama_id = sample_teams[0].id
        response = client.get(
            f"/api/games/team/{alabama_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        for game in data:
            assert (game["home_team"]["id"] == alabama_id or
                    game["away_team"]["id"] == alabama_id)

    def test_list_team_games_with_season_filter(self, client, sample_games, sample_teams, auth_headers):
        """Test listing team games filtered by season."""
        alabama_id = sample_teams[0].id
        response = client.get(
            f"/api/games/team/{alabama_id}?season=2023",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(game["season"] == 2023 for game in data)

    def test_attended_only_reaches_past_recency_window(
        self, client, auth_headers, admin_headers, db_session, cfb_league, sample_teams, test_user
    ):
        """attended_only surfaces old attended games the 100-recent window drops."""
        from datetime import datetime, timedelta
        from sports_passport.models.game import Game
        from sports_passport.models.attendance import UserGameAttendance

        team_id = sample_teams[0].id
        opponent_id = sample_teams[1].id
        # One season for all fixture games in this test, distinct from the 2023
        # sample_games fixtures, so the season query below counts only these.
        fixture_season = 2025
        base = datetime(fixture_season, 1, 1)
        games = [
            Game(
                league_id=cfb_league.id,
                source="cfbd",
                source_game_id=f"window-{i}",
                home_team_id=team_id,
                away_team_id=opponent_id,
                start_date=base + timedelta(days=i),
                season=fixture_season,
                season_type="regular",
            )
            for i in range(101)
        ]
        db_session.add_all(games)
        db_session.commit()
        oldest = games[0]
        db_session.add(UserGameAttendance(user_id=test_user.id, game_id=oldest.id))
        db_session.commit()

        # The default recency window drops the attended (oldest) game
        recent = client.get(
            f"/api/games/team/{team_id}?season={fixture_season}", headers=auth_headers
        ).json()
        assert len(recent) == 100
        assert all(g["id"] != oldest.id for g in recent)

        # attended_only returns it regardless of how far back it is
        attended = client.get(
            f"/api/games/team/{team_id}?attended_only=true", headers=auth_headers
        ).json()
        assert [g["id"] for g in attended] == [oldest.id]

        # Scoped to the caller: another user has attended nothing
        assert client.get(
            f"/api/games/team/{team_id}?attended_only=true", headers=admin_headers
        ).json() == []

        # With every game attended, a raised limit returns the full history
        # (the frontend requests limit=1000 in attended-only mode)
        db_session.add_all(
            UserGameAttendance(user_id=test_user.id, game_id=g.id) for g in games[1:]
        )
        db_session.commit()
        full = client.get(
            f"/api/games/team/{team_id}?attended_only=true&limit=1000", headers=auth_headers
        ).json()
        assert len(full) == 101

    def test_list_team_games_nonexistent_team(self, client, auth_headers):
        """Test listing games for non-existent team returns 404."""
        response = client.get("/api/games/team/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_list_team_games_requires_auth(self, client, sample_teams):
        """Test that listing team games requires authentication."""
        response = client.get(f"/api/games/team/{sample_teams[0].id}")
        assert response.status_code == 401
