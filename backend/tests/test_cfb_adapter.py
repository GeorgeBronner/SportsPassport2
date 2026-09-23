"""
Tests for the CFB adapter using mocked CollegeFootballData.com (CFBD) payloads.
"""
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.services.adapters.cfb import CfbAdapter

ALABAMA = {
    "id": 333, "school": "Alabama", "mascot": "Crimson Tide",
    "abbreviation": "ALA", "conference": "SEC", "classification": "fbs",
}
GEORGIA = {
    "id": 61, "school": "Georgia", "mascot": "Bulldogs",
    "abbreviation": "UGA", "conference": "SEC", "classification": "fbs",
}
# Real CFBD payload shape for a below-FCS opponent, matching the schools that
# wedged CFB's nightly sync in docs/open_issues.md #14: present in CFBD's
# unfiltered /teams, absent from /teams/fbs and classification=fcs, and
# carrying classification: null rather than a missing key.
ROCKY_MOUNTAIN = {
    "id": 2826, "school": "Rocky Mountain", "mascot": "Battlin' Bears",
    "abbreviation": None, "conference": None, "classification": None,
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


def _fake_get(fbs_teams=None, fcs_teams=None, other_teams=None, games=None, games_by_year=None,
              venues=None):
    fbs_teams = fbs_teams if fbs_teams is not None else [ALABAMA, GEORGIA]
    fcs_teams = fcs_teams if fcs_teams is not None else []
    other_teams = other_teams if other_teams is not None else []
    games = games if games is not None else []
    games_by_year = games_by_year or {}
    venues = venues if venues is not None else []

    async def fake_get(endpoint, params=None):
        if endpoint == "/teams/fbs":
            return fbs_teams
        if endpoint == "/teams":
            if (params or {}).get("classification") == "fcs":
                return fcs_teams
            return other_teams
        if endpoint == "/venues":
            return venues
        if endpoint == "/games":
            if games_by_year:
                return games_by_year.get((params or {}).get("year"), [])
            return games
        raise AssertionError(f"unexpected endpoint {endpoint} {params}")

    return fake_get


@pytest.fixture
def adapter(db_session):
    return CfbAdapter(db_session)


class TestCfbImportTeams:
    @pytest.mark.asyncio
    async def test_import_teams_imports_non_fbs_fcs_opponents_best_effort(
        self, adapter, db_session, cfb_league
    ):
        fake = _fake_get(other_teams=[ROCKY_MOUNTAIN])
        with patch.object(adapter, "_get", AsyncMock(side_effect=fake)):
            result = await adapter.import_teams()

        assert not result.errors
        team = db_session.query(Team).filter(Team.source_team_id == "2826").one()
        assert team.name == "Rocky Mountain"
        # CFBD sends classification: null (a present key, not a missing one)
        # for a school it hasn't put in a division — the default only kicks
        # in via `or`, not dict.get's missing-key default.
        assert team.classification == "other"


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

    @pytest.mark.asyncio
    async def test_import_season_resolves_a_below_fcs_opponent_from_the_catch_all_import(
        self, adapter, db_session, cfb_league
    ):
        # Regression for docs/open_issues.md #14: an FBS "money game" against
        # a school like Rocky Mountain used to be unmatched forever because
        # import_teams never asked CFBD for anything below FCS.
        money_game = _game(id=3, awayId=2826, awayTeam="Rocky Mountain")
        fake = _fake_get(other_teams=[ROCKY_MOUNTAIN], games=[money_game])
        with patch.object(adapter, "_get", AsyncMock(side_effect=fake)):
            await adapter.import_teams()
            result = await adapter.import_season(2023)

        assert result.games_imported == 1
        assert not result.errors


class TestCfbSyncRecent:
    @pytest.mark.asyncio
    async def test_sync_recent_covers_every_season_in_the_window(self, adapter, db_session, cfb_league):
        # since (Jan 2024) is in the 2023 season; "today" (Sep 2024) is in
        # the 2024 season — the window spans the boundary, so both seasons'
        # games must be fetched, not just whichever season `since` landed in.
        game_2023 = _game(id=1)
        game_2024 = _game(id=2, startDate="2024-09-07T19:00:00.000Z")
        games_by_year = {2023: [game_2023], 2024: [game_2024]}

        with patch.object(adapter, "_get", AsyncMock(side_effect=_fake_get(games_by_year=games_by_year))):
            await adapter.import_teams()
            with patch("sports_passport.services.adapters.cfb.date") as mock_date:
                mock_date.today.return_value = date(2024, 9, 1)
                result = await adapter.sync_recent(since=date(2024, 1, 15))

        assert result.games_imported == 2
        assert not result.errors
        assert db_session.query(Game).filter(Game.source_game_id == "1").one().season == 2023
        assert db_session.query(Game).filter(Game.source_game_id == "2").one().season == 2024

    @pytest.mark.asyncio
    async def test_sync_recent_refreshes_teams_itself_without_a_prior_import_teams_call(
        self, adapter, db_session, cfb_league
    ):
        # Regression for docs/open_issues.md #14: the nightly scheduler only
        # ever calls sync_recent, never import_teams directly, so the roster
        # refresh has to happen inside sync_recent itself or a newly-seen
        # opponent stays unmatched every night until the next historical/
        # admin re-import.
        money_game = _game(id=4, awayId=2826, awayTeam="Rocky Mountain")
        fake = _fake_get(other_teams=[ROCKY_MOUNTAIN], games_by_year={2024: [money_game]})

        with patch.object(adapter, "_get", AsyncMock(side_effect=fake)):
            with patch("sports_passport.services.adapters.cfb.date") as mock_date:
                mock_date.today.return_value = date(2024, 9, 1)
                result = await adapter.sync_recent(since=date(2024, 8, 1))

        assert result.games_imported == 1
        assert not result.errors
