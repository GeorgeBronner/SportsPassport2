"""
Tests for the CBB adapter using mocked CollegeBasketballData.com (CBBD)
payloads (shapes verified against the live API on 2026-07-12, using the
existing CFBD key — confirmed to work unmodified as a CBBD bearer token).
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, patch

from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue
from sports_passport.services.adapters.cbb import CbbAdapter

ARIZONA = {
    "id": 11, "sourceId": "1", "school": "Arizona", "mascot": "Wildcats",
    "abbreviation": "ARIZ", "currentVenueId": 5, "currentVenue": "McKale Center",
    "currentCity": "Tucson", "currentState": "AZ", "conferenceId": 33, "conference": "Pac-12",
}
MARYLAND = {
    "id": 160, "sourceId": "2", "school": "Maryland", "mascot": "Terrapins",
    "abbreviation": "MD", "currentVenueId": 8, "currentVenue": "Xfinity Center",
    "currentCity": "College Park", "currentState": "MD", "conferenceId": 2, "conference": "ACC",
}
HOWARD = {
    "id": 114, "sourceId": "3", "school": "Howard", "mascot": "Bison",
    "abbreviation": "HOW", "currentVenueId": 20, "currentVenue": "Burr Gymnasium",
    "currentCity": "Washington", "currentState": "DC", "conferenceId": 18, "conference": "MEAC",
}
# Non-D-I buy-game opponent: real shape has null venue/city/state/conference
SPALDING = {
    "id": 831, "sourceId": "4", "school": "Spalding", "mascot": "Pelicans",
    "abbreviation": "SPALD", "currentVenueId": None, "currentVenue": None,
    "currentCity": None, "currentState": None, "conferenceId": None, "conference": None,
}

TEAMS_SEASON_ROSTER = [ARIZONA, MARYLAND, HOWARD]  # D-I-only, season-scoped
TEAMS_FULL_REGISTRY = [ARIZONA, MARYLAND, HOWARD, SPALDING]  # all-time, incl. non-D-I


def _game(**over):
    row = {
        "id": 1, "sourceId": "x", "season": 2024, "seasonType": "regular",
        "tournament": None, "startDate": "2023-11-08T00:00:00.000Z", "startTimeTbd": False,
        "neutralSite": False, "status": "final", "attendance": 8000,
        "homeTeamId": 11, "homeTeam": "Arizona", "homeConference": "Pac-12",
        "homePoints": 71,
        "awayTeamId": 160, "awayTeam": "Maryland", "awayConference": "ACC",
        "awayPoints": 63,
        "venueId": 5, "venue": "McKale Center", "city": "Tucson", "state": "AZ",
    }
    row.update(over)
    return row


GAME_REGULAR = _game()

GAME_BUYGAME = _game(
    id=2, season=2024, startDate="2023-11-06T16:00:00.000Z",
    homeTeamId=114, homeTeam="Howard", homeConference="MEAC", homePoints=68,
    awayTeamId=831, awayTeam="Spalding", awayConference=None, awayPoints=63,
    venueId=20, venue="Burr Gymnasium", city="Washington", state="DC",
    attendance=0,
)

GAME_POSTSEASON = _game(
    id=3, seasonType="postseason", tournament="NCAA",
    startDate="2024-03-19T22:40:00.000Z", neutralSite=True,
)

GAME_NOT_FINAL = _game(id=4, status="scheduled")

GAME_TBD_TIME = _game(id=5, startTimeTbd=True)


def _fake_get(teams_season=None, teams_registry=None, games_by_range=None):
    teams_season = teams_season if teams_season is not None else TEAMS_SEASON_ROSTER
    teams_registry = teams_registry if teams_registry is not None else TEAMS_FULL_REGISTRY
    games_by_range = games_by_range or {}

    async def fake_get(endpoint, params=None):
        params = params or {}
        if endpoint == "/teams":
            if "season" in params:
                return teams_season
            return teams_registry
        if endpoint == "/games":
            key = (params.get("startDateRange"), params.get("endDateRange"))
            return games_by_range.get(key, [])
        raise AssertionError(f"unexpected endpoint {endpoint} {params}")

    return fake_get


@pytest.fixture
def adapter(db_session):
    return CbbAdapter(db_session)


class TestCbbImportTeams:
    @pytest.mark.asyncio
    async def test_import_teams(self, adapter, db_session, cbb_league):
        with patch.object(adapter, "_get", AsyncMock(side_effect=_fake_get())):
            result = await adapter.import_teams()

        assert result.teams_imported == 3
        arizona = db_session.query(Team).filter(Team.name == "Arizona").one()
        assert arizona.classification == "d1"
        assert arizona.nickname == "Wildcats"
        assert arizona.city == "Tucson"
        assert arizona.league_id == cbb_league.id

    @pytest.mark.asyncio
    async def test_import_teams_idempotent(self, adapter, db_session):
        with patch.object(adapter, "_get", AsyncMock(side_effect=_fake_get())):
            await adapter.import_teams()
            result = await adapter.import_teams()
        assert result.teams_imported == 0
        assert db_session.query(Team).count() == 3


class TestCbbImportHistorical:
    @pytest.mark.asyncio
    async def test_import_historical_d1_vs_d1(self, adapter, db_session):
        games_by_range = {("2023-11-01", "2023-12-01"): [GAME_REGULAR]}
        with patch.object(adapter, "_get", AsyncMock(side_effect=_fake_get(games_by_range=games_by_range))):
            result = await adapter.import_historical(2023, 2023)

        assert result.games_imported == 1
        assert not result.errors
        game = db_session.query(Game).filter(Game.source_game_id == "1").one()
        # CBBD season 2024 (end year) -> our start-year convention 2023
        assert game.season == 2023
        assert game.season_type == "regular"
        assert (game.home_score, game.away_score) == (71, 63)
        assert game.venue.name == "McKale Center"
        assert game.venue.city == "Tucson"

    @pytest.mark.asyncio
    async def test_import_historical_buy_game_non_d1_opponent(self, adapter, db_session):
        games_by_range = {("2023-11-01", "2023-12-01"): [GAME_BUYGAME]}
        with patch.object(adapter, "_get", AsyncMock(side_effect=_fake_get(games_by_range=games_by_range))):
            result = await adapter.import_historical(2023, 2023)

        assert result.games_imported == 1
        assert not result.errors
        spalding = db_session.query(Team).filter(Team.name == "Spalding").one()
        assert spalding.classification == "non-d1"
        assert spalding.nickname == "Pelicans"  # metadata came from the full registry
        assert spalding.city is None  # no location data for non-D-I opponents
        howard = db_session.query(Team).filter(Team.name == "Howard").one()
        assert howard.classification == "d1"

        game = db_session.query(Game).filter(Game.source_game_id == "2").one()
        assert game.attendance is None  # CBBD's 0 means "unknown", not literally zero

    @pytest.mark.asyncio
    async def test_import_historical_postseason_and_skips(self, adapter, db_session):
        games_by_range = {
            ("2024-03-01", "2024-04-01"): [GAME_POSTSEASON, GAME_NOT_FINAL],
            ("2023-11-01", "2023-12-01"): [GAME_TBD_TIME],
        }
        with patch.object(adapter, "_get", AsyncMock(side_effect=_fake_get(games_by_range=games_by_range))):
            result = await adapter.import_historical(2023, 2023)

        # postseason game + the has_time game import; the "scheduled" (not
        # final) game must be skipped entirely
        assert result.games_imported == 2
        assert db_session.query(Game).filter(Game.source_game_id == "4").count() == 0

        postseason_game = db_session.query(Game).filter(Game.source_game_id == "3").one()
        assert postseason_game.season_type == "postseason"
        assert postseason_game.neutral_site is True

        tbd_game = db_session.query(Game).filter(Game.source_game_id == "5").one()
        assert tbd_game.has_time is False


class TestCbbSync:
    @pytest.mark.asyncio
    async def test_sync_recent_resolves_onto_historical_row(self, adapter, db_session):
        games_by_range = {("2023-11-01", "2023-12-01"): [GAME_REGULAR]}
        with patch.object(adapter, "_get", AsyncMock(side_effect=_fake_get(games_by_range=games_by_range))):
            await adapter.import_historical(2023, 2023)

        updated = dict(GAME_REGULAR, homePoints=80, awayPoints=75)
        with patch.object(
            adapter, "_get",
            AsyncMock(side_effect=_fake_get(games_by_range={("2023-11-06", "2026-07-13"): [updated]})),
        ):
            with patch("sports_passport.services.adapters.cbb.date") as mock_date:
                mock_date.today.return_value = date(2026, 7, 12)
                result = await adapter.sync_recent(since=date(2023, 11, 6))

        assert result.games_imported == 0
        assert result.games_updated == 1
        game = db_session.query(Game).filter(Game.source_game_id == "1").one()
        assert (game.home_score, game.away_score) == (80, 75)
