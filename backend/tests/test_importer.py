"""
Tests for the shared importer helpers and multi-league behavior.
"""
import pytest
from datetime import datetime

from sports_passport.models.team import Team
from sports_passport.models.game import Game
from sports_passport.services.importer import get_league, upsert_team, upsert_venue, upsert_game


class TestUpserts:
    """Importer upserts must be idempotent on (source, source_*_id)."""

    def test_upsert_team_create_then_update(self, db_session, nhl_league):
        team, created = upsert_team(
            db_session, source="nhl", source_team_id="HFD",
            league_id=nhl_league.id, name="Hartford Whalers", abbreviation="HFD",
        )
        assert created is True

        team2, created2 = upsert_team(
            db_session, source="nhl", source_team_id="HFD",
            league_id=nhl_league.id, name="Hartford Whalers", last_season=1996,
        )
        assert created2 is False
        assert team2.id == team.id
        assert team2.last_season == 1996
        assert team2.abbreviation == "HFD"  # None fields don't clobber existing values

    def test_upsert_venue_idempotent(self, db_session):
        v1, c1 = upsert_venue(db_session, source="nhl", source_venue_id="MSG",
                              name="Madison Square Garden", city="New York")
        v2, c2 = upsert_venue(db_session, source="nhl", source_venue_id="MSG",
                              name="Madison Square Garden")
        assert (c1, c2) == (True, False)
        assert v1.id == v2.id

    def test_upsert_game_updates_scores(self, db_session, nhl_league, sample_nhl_teams):
        game, created = upsert_game(
            db_session, source="nhl", source_game_id="1994030417",
            league_id=nhl_league.id,
            home_team_id=sample_nhl_teams[0].id,
            away_team_id=sample_nhl_teams[1].id,
            start_date=datetime(1994, 6, 14),
            season=1993, season_type="postseason",
            home_score=None, away_score=None,
        )
        assert created is True

        # Sync run later fills in the final score
        game2, created2 = upsert_game(
            db_session, source="nhl", source_game_id="1994030417",
            league_id=nhl_league.id,
            home_team_id=sample_nhl_teams[0].id,
            away_team_id=sample_nhl_teams[1].id,
            start_date=datetime(1994, 6, 14),
            season=1993, season_type="postseason",
            home_score=3, away_score=2,
        )
        assert created2 is False
        assert game2.id == game.id
        assert (game2.home_score, game2.away_score) == (3, 2)
        db_session.commit()
        assert db_session.query(Game).count() == 1

    def test_same_source_id_different_sources_are_distinct(self, db_session, cfb_league, nhl_league):
        upsert_team(db_session, source="cfbd", source_team_id="42",
                    league_id=cfb_league.id, name="Some School")
        upsert_team(db_session, source="nhl", source_team_id="42",
                    league_id=nhl_league.id, name="Some Club")
        db_session.commit()
        assert db_session.query(Team).count() == 2

    def test_get_league_unknown_raises(self, db_session):
        with pytest.raises(ValueError):
            get_league(db_session, "MLS")


class TestMultiLeagueFilters:
    """Games endpoints must separate leagues cleanly."""

    def test_list_games_filtered_by_league(self, client, sample_games, sample_nhl_games, auth_headers):
        response = client.get("/api/games/?league=NHL", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["league"]["code"] == "NHL"

        response = client.get("/api/games/?league=CFB", headers=auth_headers)
        assert len(response.json()) == 3

    def test_list_games_all_leagues(self, client, sample_games, sample_nhl_games, auth_headers):
        response = client.get("/api/games/", headers=auth_headers)
        assert len(response.json()) == 4

    def test_unknown_league_404(self, client, sample_games, auth_headers):
        response = client.get("/api/games/?league=MLS", headers=auth_headers)
        assert response.status_code == 404

    def test_leagues_endpoint(self, client, auth_headers, db_session):
        response = client.get("/api/leagues/", headers=auth_headers)
        assert response.status_code == 200
        codes = [row["code"] for row in response.json()]
        assert codes == ["CFB", "MLB", "NBA", "NFL", "NHL"]

    def test_teams_filtered_by_league(self, client, sample_teams, sample_nhl_teams, auth_headers):
        response = client.get("/api/teams/?league=NHL", headers=auth_headers)
        assert response.status_code == 200
        names = [t["name"] for t in response.json()]
        assert names == ["Boston Bruins", "New York Rangers"]


class TestMultiLeagueStats:
    """Attendance stats must aggregate across leagues."""

    def test_stats_include_league_breakdown(
        self, client, db_session, test_user, auth_headers,
        sample_attendance, sample_nhl_games
    ):
        from sports_passport.models.attendance import UserGameAttendance
        db_session.add(UserGameAttendance(
            user_id=test_user.id,
            game_id=sample_nhl_games[0].id,
            notes="OT winner!"
        ))
        db_session.commit()

        response = client.get("/api/attendance/stats", headers=auth_headers)
        assert response.status_code == 200
        stats = response.json()
        assert stats["total_games"] == 3
        assert stats["games_by_league"] == {"CFB": 2, "NHL": 1}
        # Pro teams count in games_by_team; venue set spans both leagues
        assert stats["games_by_team"]["New York Rangers"] == 1
        assert "Madison Square Garden" in stats["stadiums_visited"]
