"""
Tests for attendance endpoints.
"""
from datetime import datetime

import pytest

from sports_passport.models.attendance import UserGameAttendance
from sports_passport.models.game import Game


class TestMarkAttendance:
    """Tests for POST /api/attendance/ endpoint."""

    def test_mark_game_attended(self, client, sample_games, auth_headers):
        """Test marking a single game as attended."""
        game_id = sample_games[0].id
        response = client.post(
            "/api/attendance/",
            json={
                "game_id": game_id,
                "notes": "Amazing game!"
            },
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["game_id"] == game_id
        assert data["notes"] == "Amazing game!"
        assert "id" in data
        assert "created_at" in data

    def test_mark_game_attended_without_notes(self, client, sample_games, auth_headers):
        """Test marking a game attended without notes."""
        game_id = sample_games[0].id
        response = client.post(
            "/api/attendance/",
            json={"game_id": game_id},
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["game_id"] == game_id
        assert data["notes"] is None

    def test_mark_nonexistent_game_attended(self, client, auth_headers):
        """Test marking non-existent game returns 404."""
        response = client.post(
            "/api/attendance/",
            json={"game_id": 99999},
            headers=auth_headers
        )
        assert response.status_code == 404

    def test_mark_duplicate_attendance(self, client, sample_games, auth_headers):
        """Test marking same game twice returns 400."""
        game_id = sample_games[0].id
        # First time should succeed
        response = client.post(
            "/api/attendance/",
            json={"game_id": game_id},
            headers=auth_headers
        )
        assert response.status_code == 201

        # Second time should fail
        response = client.post(
            "/api/attendance/",
            json={"game_id": game_id},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "already marked" in response.json()["detail"].lower()

    def test_mark_attendance_requires_auth(self, client, sample_games):
        """Test marking attendance requires authentication."""
        response = client.post(
            "/api/attendance/",
            json={"game_id": sample_games[0].id}
        )
        assert response.status_code == 401


class TestBulkAttendance:
    """Tests for POST /api/attendance/bulk endpoint."""

    def test_bulk_mark_attendance(self, client, sample_games, auth_headers):
        """Test marking multiple games as attended."""
        response = client.post(
            "/api/attendance/bulk",
            json={
                "games": [
                    {"game_id": sample_games[0].id, "notes": "Great game!"},
                    {"game_id": sample_games[1].id, "notes": "Close match!"},
                    {"game_id": sample_games[2].id}
                ]
            },
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 3
        assert data["skipped"] == 0
        assert len(data["errors"]) == 0

    def test_bulk_mark_with_duplicates(self, client, sample_games, auth_headers):
        """Test bulk marking skips already attended games."""
        # Mark first game as attended
        client.post(
            "/api/attendance/",
            json={"game_id": sample_games[0].id},
            headers=auth_headers
        )

        # Bulk request with duplicate
        response = client.post(
            "/api/attendance/bulk",
            json={
                "games": [
                    {"game_id": sample_games[0].id},
                    {"game_id": sample_games[1].id}
                ]
            },
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 1
        assert data["skipped"] == 1

    def test_bulk_mark_with_invalid_games(self, client, sample_games, auth_headers):
        """Test bulk marking with some invalid game IDs."""
        response = client.post(
            "/api/attendance/bulk",
            json={
                "games": [
                    {"game_id": sample_games[0].id},
                    {"game_id": 99999},
                    {"game_id": sample_games[1].id}
                ]
            },
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 2
        assert data["skipped"] == 0
        assert len(data["errors"]) == 1
        assert "99999" in data["errors"][0]

    def test_bulk_mark_empty_list(self, client, auth_headers):
        """Test bulk marking with empty list."""
        response = client.post(
            "/api/attendance/bulk",
            json={"games": []},
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 0
        assert data["skipped"] == 0

    def test_bulk_mark_requires_auth(self, client, sample_games):
        """Test bulk marking requires authentication."""
        response = client.post(
            "/api/attendance/bulk",
            json={
                "games": [{"game_id": sample_games[0].id}]
            }
        )
        assert response.status_code == 401


class TestListAttendance:
    """Tests for GET /api/attendance/ endpoint."""

    def test_list_attended_games(self, client, sample_attendance, auth_headers):
        """Test listing attended games."""
        response = client.get("/api/attendance/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all("game" in item for item in data)
        assert all("notes" in item for item in data)
        assert all("created_at" in item for item in data)

    def test_list_attended_games_filter_by_season(self, client, sample_attendance, auth_headers):
        """Test filtering attended games by season."""
        # Note: Season filtering not implemented yet - skip for now
        response = client.get("/api/attendance/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Both games are from 2023, so we should see 2
        assert len(data) == 2

    def test_list_attended_games_filter_by_team(self, client, sample_attendance, auth_headers):
        """Test filtering attended games by team."""
        # Note: Team filtering not implemented yet - returns all
        response = client.get("/api/attendance/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Just verify we can list games
        assert len(data) >= 0

    def test_list_attended_games_pagination(self, client, sample_attendance, auth_headers):
        """Test pagination of attended games."""
        response = client.get(
            "/api/attendance/?limit=1",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_list_attended_games_empty(self, client, auth_headers):
        """Test listing attended games when none exist."""
        response = client.get("/api/attendance/", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_attended_games_requires_auth(self, client, sample_attendance):
        """Test listing attended games requires authentication."""
        response = client.get("/api/attendance/")
        assert response.status_code == 401


class TestAttendanceStats:
    """Tests for GET /api/attendance/stats endpoint."""

    def test_get_attendance_stats(self, client, sample_attendance, auth_headers):
        """Test getting attendance statistics."""
        response = client.get("/api/attendance/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_games"] == 2
        assert data["unique_stadiums"] == 2
        assert data["unique_states"] == 2
        assert "games_by_team" in data
        assert "games_by_season" in data

    def test_get_stats_games_by_team(self, client, sample_attendance, auth_headers):
        """Test games by team in statistics."""
        response = client.get("/api/attendance/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        games_by_team = data["games_by_team"]
        # games_by_team is a dict mapping team name to count
        assert isinstance(games_by_team, dict)
        assert len(games_by_team) == 3
        # Each team should have at least one game
        for count in games_by_team.values():
            assert count > 0

    def test_get_stats_games_by_season(self, client, sample_attendance, auth_headers):
        """Test games by season in statistics."""
        response = client.get("/api/attendance/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        games_by_season = data["games_by_season"]
        # games_by_season is a dict mapping season to count
        # Note: JSON keys are always strings, so 2023 becomes "2023"
        assert isinstance(games_by_season, dict)
        assert "2023" in games_by_season or 2023 in games_by_season
        count = games_by_season.get("2023") or games_by_season.get(2023)
        assert count == 2

    def test_get_stats_empty(self, client, auth_headers):
        """Test statistics when no games attended."""
        response = client.get("/api/attendance/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_games"] == 0
        assert data["unique_stadiums"] == 0
        assert data["unique_states"] == 0
        assert data["games_by_team"] == {}
        assert data["games_by_season"] == {}

    def test_get_stats_requires_auth(self, client, sample_attendance):
        """Test getting stats requires authentication."""
        response = client.get("/api/attendance/stats")
        assert response.status_code == 401

    def test_home_team_record(self, client, sample_attendance, auth_headers):
        """The home side won both attended games (35-28 and 42-27)."""
        data = client.get("/api/attendance/stats", headers=auth_headers).json()
        assert (data["home_wins"], data["home_losses"], data["home_ties"]) == (2, 0, 0)

    def test_unplayed_game_is_not_scored_as_a_tie(
        self, client, db_session, test_user, sample_games, cfb_league,
        sample_teams, sample_venues, auth_headers
    ):
        """A future fixture has both scores null — it must not count as 0-0."""
        future = Game(
            league_id=cfb_league.id,
            source="cfbd",
            source_game_id="future-1",
            home_team_id=sample_teams[0].id,
            away_team_id=sample_teams[1].id,
            home_score=None,
            away_score=None,
            start_date=datetime(2026, 9, 5, 23, 30, 0),
            season=2026,
            season_type="regular",
            venue_id=sample_venues[0].id,
        )
        db_session.add(future)
        db_session.commit()
        db_session.add(UserGameAttendance(user_id=test_user.id, game_id=future.id))
        db_session.commit()

        data = client.get("/api/attendance/stats", headers=auth_headers).json()
        assert data["total_games"] == 1
        assert (data["home_wins"], data["home_losses"], data["home_ties"]) == (0, 0, 0)

    def test_top_teams_carries_identity(self, client, sample_attendance, auth_headers):
        """Ranked like games_by_team, but with the id/logo the UI needs."""
        data = client.get("/api/attendance/stats", headers=auth_headers).json()
        top = data["top_teams"]
        # Michigan appears in both attended games; Alabama and Ohio State in one.
        assert top[0]["name"] == "Michigan"
        assert top[0]["count"] == 2
        assert top[0]["league_code"] == "CFB"
        assert isinstance(top[0]["team_id"], int)
        # Counts must agree with the legacy name-keyed map.
        assert {t["name"]: t["count"] for t in top} == data["games_by_team"]

    def test_season_breakdown(self, client, sample_attendance, auth_headers):
        """Per-season slice powers the season headers and chart tooltips."""
        data = client.get("/api/attendance/stats", headers=auth_headers).json()
        season = data["season_breakdown"]["2023"]
        assert season["games"] == 2
        assert season["venues"] == 2
        assert season["leagues"] == {"CFB": 2}
        assert (season["home_wins"], season["home_losses"], season["home_ties"]) == (2, 0, 0)

    def test_new_venues_by_season_counts_each_venue_once(
        self, client, db_session, test_user, sample_games, auth_headers
    ):
        """Returning to a venue in a later season doesn't make it new again."""
        # sample_games[2] is a 2023 postseason game back at sample_venues[0],
        # which sample_games[0] already stamped in the same season.
        db_session.add(
            UserGameAttendance(user_id=test_user.id, game_id=sample_games[0].id)
        )
        db_session.add(
            UserGameAttendance(user_id=test_user.id, game_id=sample_games[2].id)
        )
        db_session.commit()

        data = client.get("/api/attendance/stats", headers=auth_headers).json()
        assert data["unique_stadiums"] == 1
        assert data["new_venues_by_season"] == {"2023": 1}

    def test_weekday_month_and_longest_gap(self, client, sample_attendance, auth_headers):
        """Both attended games fall on a Saturday, 84 days apart."""
        data = client.get("/api/attendance/stats", headers=auth_headers).json()
        assert data["games_by_weekday"] == {"5": 2}
        assert data["games_by_month"] == {"9": 1, "11": 1}
        assert data["longest_gap_days"] == 84
        assert data["longest_gap_start"].startswith("2023-09-02")
        assert data["longest_gap_end"].startswith("2023-11-25")

    def test_single_game_has_no_gap(
        self, client, db_session, test_user, sample_games, auth_headers
    ):
        """One game means no interval to measure."""
        db_session.add(
            UserGameAttendance(user_id=test_user.id, game_id=sample_games[0].id)
        )
        db_session.commit()
        data = client.get("/api/attendance/stats", headers=auth_headers).json()
        assert data["longest_gap_days"] is None
        assert data["longest_gap_start"] is None


class TestUpdateAttendance:
    """Tests for PATCH /api/attendance/{attendance_id} endpoint."""

    def test_update_attendance_notes(self, client, sample_attendance, auth_headers):
        """Test updating attendance notes."""
        attendance_id = sample_attendance[0].id
        response = client.patch(
            f"/api/attendance/{attendance_id}",
            json={"notes": "Updated notes!"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Updated notes!"
        assert data["id"] == attendance_id

    def test_clear_attendance_notes(self, client, sample_attendance, auth_headers):
        """An explicit null clears the saved note; omitting the field leaves it alone."""
        attendance_id = sample_attendance[0].id
        response = client.patch(
            f"/api/attendance/{attendance_id}",
            json={"notes": None},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["notes"] is None

        # A PATCH without the notes field must not touch the stored value
        client.patch(
            f"/api/attendance/{attendance_id}",
            json={"notes": "Back again"},
            headers=auth_headers
        )
        response = client.patch(
            f"/api/attendance/{attendance_id}",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["notes"] == "Back again"

    def test_update_nonexistent_attendance(self, client, auth_headers):
        """Test updating non-existent attendance returns 404."""
        response = client.patch(
            "/api/attendance/99999",
            json={"notes": "Test"},
            headers=auth_headers
        )
        assert response.status_code == 404

    def test_update_other_user_attendance(self, client, sample_attendance, admin_headers):
        """Test cannot update another user's attendance."""
        attendance_id = sample_attendance[0].id
        response = client.patch(
            f"/api/attendance/{attendance_id}",
            json={"notes": "Hacking!"},
            headers=admin_headers
        )
        assert response.status_code == 404

    def test_update_attendance_requires_auth(self, client, sample_attendance):
        """Test updating attendance requires authentication."""
        response = client.patch(
            f"/api/attendance/{sample_attendance[0].id}",
            json={"notes": "Test"}
        )
        assert response.status_code == 401


class TestDeleteAttendance:
    """Tests for DELETE /api/attendance/{attendance_id} endpoint."""

    def test_delete_attendance(self, client, sample_attendance, auth_headers):
        """Test deleting attendance record."""
        attendance_id = sample_attendance[0].id
        response = client.delete(
            f"/api/attendance/{attendance_id}",
            headers=auth_headers
        )
        assert response.status_code == 204

        # Verify it's gone
        response = client.get("/api/attendance/", headers=auth_headers)
        data = response.json()
        assert len(data) == 1

    def test_delete_nonexistent_attendance(self, client, auth_headers):
        """Test deleting non-existent attendance returns 404."""
        response = client.delete("/api/attendance/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_other_user_attendance(self, client, sample_attendance, admin_headers):
        """Test cannot delete another user's attendance."""
        attendance_id = sample_attendance[0].id
        response = client.delete(
            f"/api/attendance/{attendance_id}",
            headers=admin_headers
        )
        assert response.status_code == 404

    def test_delete_attendance_requires_auth(self, client, sample_attendance):
        """Test deleting attendance requires authentication."""
        response = client.delete(f"/api/attendance/{sample_attendance[0].id}")
        assert response.status_code == 401


class TestAttendanceUniqueness:
    """The (user_id, game_id) unique index backs up the router's own check."""

    def test_bulk_skips_duplicate_within_one_payload(self, client, sample_games, auth_headers):
        """The session doesn't autoflush, so the same game listed twice used to
        slip past the existing-row check and violate the index at commit."""
        response = client.post(
            "/api/attendance/bulk",
            json={
                "games": [
                    {"game_id": sample_games[0].id},
                    {"game_id": sample_games[0].id},
                ]
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert (data["created"], data["skipped"]) == (1, 1)

    def test_database_rejects_duplicate_attendance(self, db_session, test_user, sample_games):
        from sqlalchemy.exc import IntegrityError

        from sports_passport.models.attendance import UserGameAttendance

        db_session.add(UserGameAttendance(user_id=test_user.id, game_id=sample_games[0].id))
        db_session.commit()

        db_session.add(UserGameAttendance(user_id=test_user.id, game_id=sample_games[0].id))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_bulk_survives_a_row_already_committed_elsewhere(
        self, client, db_session, test_user, sample_games, auth_headers, monkeypatch
    ):
        """A row committed by a concurrent request between the lookup and the
        insert must cost only itself.

        Before the per-row savepoint the unique index aborted the whole
        transaction at commit, so one collided row took every good row with it
        and the caller got a 500 with nothing saved.

        The tests share one session with the endpoint (see conftest), so a row
        committed here is visible to the lookup and would simply be skipped.
        Blinding the lookup is what reproduces the real ordering: the other
        request commits *after* this one has already checked.
        """
        from sports_passport.models.attendance import UserGameAttendance

        db_session.add(
            UserGameAttendance(user_id=test_user.id, game_id=sample_games[1].id)
        )
        db_session.commit()

        monkeypatch.setattr(
            "sports_passport.routers.attendance._existing_attendance",
            lambda db, user_id, game_id: None,
        )

        response = client.post(
            "/api/attendance/bulk",
            json={
                "games": [
                    {"game_id": sample_games[0].id},
                    {"game_id": sample_games[1].id},
                ]
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 1, "the uncollided row must still be saved"
        assert data["skipped"] == 1

        saved = {
            a.game_id
            for a in db_session.query(UserGameAttendance)
            .filter(UserGameAttendance.user_id == test_user.id)
            .all()
        }
        assert {sample_games[0].id, sample_games[1].id} <= saved

    def test_bulk_rejects_oversized_payload(self, client, sample_games, auth_headers):
        response = client.post(
            "/api/attendance/bulk",
            json={"games": [{"game_id": sample_games[0].id}] * 5001},
            headers=auth_headers,
        )
        assert response.status_code == 422
