"""
Tests for the CFB adapter using mocked CollegeFootballData.com (CFBD) payloads.
"""
from unittest.mock import AsyncMock, patch

import pytest

from sports_passport.models.game import Game
from sports_passport.services.adapters.cfb import CfbAdapter

ALABAMA = {
    "id": 333, "school": "Alabama", "mascot": "Crimson Tide",
    "abbreviation": "ALA", "conference": "SEC", "classification": "fbs",
}
GEORGIA = {
    "id": 61, "school": "Georgia", "mascot": "Bulldogs",
    "abbreviation": "UGA", "conference": "SEC", "classification": "fbs",
}


def _game(**over):
    row = {
        "id": 1, "startDate": "2023-09-02T19:00:00.000Z", "seasonType": "regular", "week": 1,
        "homeId": 333, "homeTeam": "Alabama", "homePoints": 31,
        "awayId": 61, "awayTeam": "Georgia", "awayPoints": 24,
        "venueId": None, "neutralSite": False, "attendance": 100000,
    }
    row.update(over)
    return row


def _fake_get(fbs_teams=None, fcs_teams=None, games=None, venues=None):
    fbs_teams = fbs_teams if fbs_teams is not None else [ALABAMA, GEORGIA]
    fcs_teams = fcs_teams if fcs_teams is not None else []
    games = games if games is not None else []
    venues = venues if venues is not None else []

    async def fake_get(endpoint, params=None):
        if endpoint == "/teams/fbs":
            return fbs_teams
        if endpoint == "/teams":
            return fcs_teams
        if endpoint == "/venues":
            return venues
        if endpoint == "/games":
            return games
        raise AssertionError(f"unexpected endpoint {endpoint} {params}")

    return fake_get


@pytest.fixture
def adapter(db_session):
    return CfbAdapter(db_session)


class TestCfbImportSeason:
    @pytest.mark.asyncio
    async def test_import_season_resolves_teams_by_source_id(self, adapter, db_session, cfb_league):
        with patch.object(adapter, "_get", AsyncMock(side_effect=_fake_get(games=[_game()]))):
            await adapter.import_teams()
            result = await adapter.import_season(2023)

        assert result.games_imported == 1
        assert not result.errors
        game = db_session.query(Game).filter(Game.source_game_id == "1").one()
        assert (game.home_score, game.away_score) == (31, 24)

    @pytest.mark.asyncio
    async def test_import_season_records_unmatched_team_as_error(self, adapter, db_session, cfb_league):
        unmatched = _game(id=2, homeId=999, homeTeam="Some FCS School")
        with patch.object(adapter, "_get", AsyncMock(side_effect=_fake_get(games=[unmatched]))):
            await adapter.import_teams()
            result = await adapter.import_season(2023)

        assert result.games_imported == 0
        assert len(result.errors) == 1
        assert "unmatched team" in result.errors[0]
        assert db_session.query(Game).count() == 0
