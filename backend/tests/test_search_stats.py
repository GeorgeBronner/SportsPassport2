"""Tests for cross-league team search and attendance-stats endpoints (Phase 2)."""
from datetime import datetime

import pytest

from sports_passport.models.team import Team
from sports_passport.models.game import Game
from sports_passport.models.attendance import UserGameAttendance


@pytest.fixture
def attended_games(client, auth_headers, sample_games, sample_nhl_games):
    """Mark two CFB games (one Alabama win, one loss... actually both wins) attended."""
    # sample_games[0]: Alabama 35, Michigan 28 (Alabama W / Michigan L)
    # sample_games[1]: Michigan 42, Ohio State 27 (Michigan W)
    for game in (sample_games[0], sample_games[1]):
        resp = client.post("/api/attendance/", json={"game_id": game.id}, headers=auth_headers)
        assert resp.status_code == 201
    return [sample_games[0], sample_games[1]]


class TestTeamSearch:
    def test_requires_auth(self, client, sample_teams):
        assert client.get("/api/teams/search?q=alabama").status_code == 401

    def test_finds_across_leagues(self, client, auth_headers, sample_teams, sample_nhl_teams):
        resp = client.get("/api/teams/search?q=bo", headers=auth_headers)
        assert resp.status_code == 200
        results = resp.json()
        codes = {(r["name"], r["league_code"]) for r in results}
        assert ("Boston Bruins", "NHL") in codes

    def test_matches_nickname_and_city(self, client, auth_headers, sample_nhl_teams):
        by_nick = client.get("/api/teams/search?q=bruins", headers=auth_headers).json()
        assert any(r["name"] == "Boston Bruins" for r in by_nick)
        by_city = client.get("/api/teams/search?q=new york", headers=auth_headers).json()
        assert any(r["name"] == "New York Rangers" for r in by_city)

    def test_league_filter(self, client, auth_headers, sample_teams, sample_nhl_teams):
        resp = client.get("/api/teams/search?q=new york&league=NHL", headers=auth_headers)
        assert resp.status_code == 200
        results = resp.json()
        assert results and all(r["league_code"] == "NHL" for r in results)
        # Same query filtered to CFB matches nothing
        assert client.get("/api/teams/search?q=new york&league=CFB", headers=auth_headers).json() == []

    def test_attended_count_and_ranking(self, client, auth_headers, sample_teams, sample_nhl_teams, attended_games):
        # "an" matches Michigan (2 attended games) and New York Rangers (0)
        resp = client.get("/api/teams/search?q=an", headers=auth_headers)
        results = resp.json()
        michigan = next(r for r in results if r["name"] == "Michigan")
        assert michigan["attended_count"] == 2
        # Attended team ranks above non-attended matches
        assert results[0]["name"] == "Michigan"

    def test_min_query_length(self, client, auth_headers):
        assert client.get("/api/teams/search?q=a", headers=auth_headers).status_code == 422

    def test_limit_bounds(self, client, auth_headers):
        assert client.get("/api/teams/search?q=bo&limit=0", headers=auth_headers).status_code == 422
        assert client.get("/api/teams/search?q=bo&limit=-3", headers=auth_headers).status_code == 422
        assert client.get("/api/teams/search?q=bo&limit=101", headers=auth_headers).status_code == 422

    def test_attended_team_beyond_candidate_pool(
        self, client, auth_headers, db_session, cfb_league, test_user
    ):
        """Attendance-first ranking must survive the 300-row candidate pool cap."""
        teams = [
            Team(
                league_id=cfb_league.id,
                source="cfbd",
                source_team_id=f"pool-{i}",
                name=f"Zebra College {i:03d}",
                classification="fbs",
            )
            for i in range(1, 322)
        ]
        db_session.add_all(teams)
        db_session.commit()

        # Attend a game involving the alphabetically last match — the
        # name-ordered 300-team pool would otherwise never include it.
        # The opponent doesn't match the query, so the attended credit it
        # also earns can't win on the name tiebreak instead.
        attended_team = teams[-1]
        opponent = Team(
            league_id=cfb_league.id,
            source="cfbd",
            source_team_id="pool-opp",
            name="Aardvark State",
            classification="fbs",
        )
        db_session.add(opponent)
        db_session.commit()
        game = Game(
            league_id=cfb_league.id,
            source="cfbd",
            source_game_id="pool-game",
            home_team_id=attended_team.id,
            away_team_id=opponent.id,
            start_date=datetime(2023, 10, 1),
            season=2023,
            season_type="regular",
        )
        db_session.add(game)
        db_session.commit()
        db_session.add(UserGameAttendance(user_id=test_user.id, game_id=game.id))
        db_session.commit()

        resp = client.get("/api/teams/search?q=zebra", headers=auth_headers)
        assert resp.status_code == 200
        results = resp.json()
        assert results[0]["name"] == attended_team.name
        assert results[0]["attended_count"] == 1


class TestTeamAttendanceStats:
    def test_unknown_team_404(self, client, auth_headers):
        assert client.get("/api/teams/999999/attendance-stats", headers=auth_headers).status_code == 404

    def test_empty_history(self, client, auth_headers, sample_teams):
        resp = client.get(f"/api/teams/{sample_teams[2].id}/attendance-stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["games_attended"] == 0
        assert data["wins"] == 0 and data["losses"] == 0
        assert data["venues"] == []
        assert data["first_game_date"] is None

    def test_record_seasons_venues(self, client, auth_headers, sample_teams, attended_games):
        # Michigan: lost 28-35 at Alabama, beat Ohio State 42-27 at home
        resp = client.get(f"/api/teams/{sample_teams[1].id}/attendance-stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["games_attended"] == 2
        assert data["wins"] == 1 and data["losses"] == 1 and data["ties"] == 0
        assert data["games_by_season"] == {"2023": 2}
        venue_names = {v["name"] for v in data["venues"]}
        assert venue_names == {"Bryant-Denny Stadium", "Michigan Stadium"}
        assert data["first_game_date"] < data["last_game_date"]

    def test_scoped_to_current_user(self, client, admin_headers, sample_teams, attended_games):
        # Another user sees no attendance for the same team
        resp = client.get(f"/api/teams/{sample_teams[1].id}/attendance-stats", headers=admin_headers)
        assert resp.json()["games_attended"] == 0


class TestAttendanceVenues:
    def test_empty(self, client, auth_headers):
        data = client.get("/api/attendance/venues", headers=auth_headers).json()
        assert data == {"venues": [], "games_without_venue": 0}

    def test_venue_points(self, client, auth_headers, db_session, attended_games, sample_venues):
        # Give one venue coordinates to confirm they flow through
        sample_venues[0].latitude = 33.2
        sample_venues[0].longitude = -87.5
        db_session.commit()

        data = client.get("/api/attendance/venues", headers=auth_headers).json()
        assert data["games_without_venue"] == 0
        by_name = {v["name"]: v for v in data["venues"]}
        bryant = by_name["Bryant-Denny Stadium"]
        assert bryant["count"] == 1
        assert bryant["latitude"] == 33.2
        assert bryant["leagues"] == ["CFB"]
        assert by_name["Michigan Stadium"]["longitude"] is None


class TestAttendanceStatsAdditions:
    def test_empty_stats_new_fields(self, client, auth_headers):
        data = client.get("/api/attendance/stats", headers=auth_headers).json()
        assert data["games_by_state"] == {}
        assert data["venues"] == []
        assert data["first_game_date"] is None
        assert data["last_game_date"] is None

    def test_state_and_venue_counts(self, client, auth_headers, attended_games):
        data = client.get("/api/attendance/stats", headers=auth_headers).json()
        assert data["games_by_state"] == {"Alabama": 1, "Michigan": 1}
        assert {v["name"]: v["count"] for v in data["venues"]} == {
            "Bryant-Denny Stadium": 1,
            "Michigan Stadium": 1,
        }
        assert data["first_game_date"].startswith("2023-09-02")
        assert data["last_game_date"].startswith("2023-11-25")
