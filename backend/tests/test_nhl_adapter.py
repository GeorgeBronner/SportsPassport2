"""
Tests for the NHL adapter using mocked API payloads (shapes verified against
the live API on 2026-07-11).
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, patch

from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue
from sports_passport.services.adapters.nhl import NhlAdapter

TEAMS_PAYLOAD = {
    "data": [
        {"id": 3, "franchiseId": 10, "fullName": "New York Rangers", "triCode": "NYR"},
        {"id": 20, "franchiseId": 21, "fullName": "Calgary Flames", "triCode": "CGY"},
        {"id": 33, "franchiseId": 34, "fullName": "Hartford Whalers", "triCode": "HFD"},
    ]
}

GAME_REGULAR_OT = {
    "id": 1993020518,
    "season": 19931994,
    "gameType": 2,
    "gameDate": "1994-01-05",
    "startTimeUTC": "1994-01-06T00:35:00Z",
    "venue": {"default": "Madison Square Garden"},
    "homeTeam": {"id": 3, "abbrev": "NYR", "score": 4},
    "awayTeam": {"id": 20, "abbrev": "CGY", "score": 3},
    "gameOutcome": {"lastPeriodType": "OT"},
}

GAME_PRESEASON = {
    "id": 1993010001,
    "season": 19931994,
    "gameType": 1,  # must be skipped
    "gameDate": "1993-09-20",
    "startTimeUTC": "1993-09-21T00:00:00Z",
    "venue": {"default": "Madison Square Garden"},
    "homeTeam": {"id": 3, "abbrev": "NYR", "score": 2},
    "awayTeam": {"id": 20, "abbrev": "CGY", "score": 1},
    "gameOutcome": {"lastPeriodType": "REG"},
}

STANDINGS_PAYLOAD = {
    "standings": [
        {"teamAbbrev": {"default": "NYR"}},
        {"teamAbbrev": {"default": "CGY"}},
    ]
}


def _schedule_payload(*games):
    return {"games": list(games)}


@pytest.fixture
def adapter(db_session):
    return NhlAdapter(db_session)


class TestNhlImportTeams:
    @pytest.mark.asyncio
    async def test_import_teams(self, adapter, db_session, nhl_league):
        with patch.object(adapter, "_get", AsyncMock(return_value=TEAMS_PAYLOAD)):
            result = await adapter.import_teams()

        assert result.teams_imported == 3
        whalers = db_session.query(Team).filter(Team.abbreviation == "HFD").one()
        assert whalers.name == "Hartford Whalers"
        assert whalers.franchise_id == 34
        assert whalers.league_id == nhl_league.id

    @pytest.mark.asyncio
    async def test_import_teams_idempotent(self, adapter, db_session):
        with patch.object(adapter, "_get", AsyncMock(return_value=TEAMS_PAYLOAD)):
            await adapter.import_teams()
            result = await adapter.import_teams()
        assert result.teams_imported == 0
        assert db_session.query(Team).count() == 3


class TestNhlImportSeason:
    @pytest.mark.asyncio
    async def test_import_season(self, adapter, db_session):
        async def fake_get(url, ok_404=False):
            if "stats/rest/en/team" in url:
                return TEAMS_PAYLOAD
            if "/standings/" in url:
                return STANDINGS_PAYLOAD
            if "/club-schedule-season/" in url:
                # both clubs return the same games; dedupe must handle it
                return _schedule_payload(GAME_REGULAR_OT, GAME_PRESEASON)
            raise AssertionError(f"unexpected url {url}")

        with patch.object(adapter, "_get", AsyncMock(side_effect=fake_get)), \
             patch("sports_passport.services.adapters.nhl.BACKFILL_DELAY_SECONDS", 0):
            await adapter.import_teams()
            result = await adapter.import_season(1993)

        # one regular-season game; preseason skipped; duplicate from second club deduped
        assert result.games_imported == 1
        assert result.games_updated == 0

        game = db_session.query(Game).one()
        assert game.season == 1993
        assert game.season_type == "regular"
        assert game.overtime_flag == "OT"
        assert (game.home_score, game.away_score) == (4, 3)
        assert game.source_game_id == "1993020518"
        assert game.venue.name == "Madison Square Garden"
        assert db_session.query(Venue).count() == 1

    @pytest.mark.asyncio
    async def test_import_season_no_standings(self, adapter, db_session):
        """2004-05 lockout: no standings -> no games, recorded as an error note."""
        async def fake_get(url, ok_404=False):
            if "/standings/" in url:
                return None
            return TEAMS_PAYLOAD

        with patch.object(adapter, "_get", AsyncMock(side_effect=fake_get)):
            result = await adapter.import_season(2004)

        assert result.games_imported == 0
        assert len(result.errors) == 1


class TestNhlSync:
    @pytest.mark.asyncio
    async def test_sync_recent_updates_score(self, adapter, db_session):
        async def fake_get(url, ok_404=False):
            if "stats/rest/en/team" in url:
                return TEAMS_PAYLOAD
            if "/score/" in url:
                if url.endswith("1994-01-05"):
                    return {"games": [GAME_REGULAR_OT]}
                return {"games": []}
            if "/standings/" in url:
                return STANDINGS_PAYLOAD
            raise AssertionError(f"unexpected url {url}")

        with patch.object(adapter, "_get", AsyncMock(side_effect=fake_get)), \
             patch("sports_passport.services.adapters.nhl.date") as mock_date:
            mock_date.today.return_value = date(1994, 1, 6)
            mock_date.side_effect = date
            await adapter.import_teams()
            result = await adapter.sync_recent(since=date(1994, 1, 4))

        assert result.games_imported == 1
        game = db_session.query(Game).one()
        assert game.home_score == 4
