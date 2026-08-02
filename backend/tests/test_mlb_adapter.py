"""
Tests for the MLB adapter using mocked Retrosheet CSV/gamelog rows and a
mocked MLB Stats API schedule payload (shapes verified against the live
sources on 2026-07-11).
"""
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue
from sports_passport.services.adapters.mlb import MlbAdapter

TEAMS_CSV = (
    "WAS,MON,NL,E,Montreal,Expos,,4/8/1969,10/3/2004,Montreal,QC\n"
    "WAS,WAS,NL,E,Washington,Nationals,,4/4/2005,,Washington,DC\n"
    "OAK,OAK,AL,W,Oakland,Athletics,A's,4/8/1969,9/29/2024,Oakland,CA\n"
)

PARKS_CSV = (
    "PARKID,NAME,AKA,CITY,STATE,START,END,LEAGUE,NOTES\n"
    'MON01,"Parc Jarry",,Montreal,QC,,,NL,""\n'
    'OAK01,"Oakland Coliseum",,Oakland,CA,,,AL,""\n'
)

# Retrosheet gamelog row fields, 0-indexed per glfields.txt (see mlb.py header)
GAMELOG_ROW_1970 = [
    "19700406", "0", "Tue", "OAK", "AL", "1", "MON", "NL", "1",
    "3", "2", "54", "D", "", "", "", "MON01", "12345", "150",
]

# Postseason gamelog rows use the same fixed-field format; each file spans
# all years of its series type, so import_postseason must filter by season.
POSTSEASON_ROW_1973 = [
    "19731013", "0", "Sat", "MON", "NL", "1", "OAK", "AL", "1",
    "2", "3", "66", "D", "", "", "", "OAK01", "46021", "195",
]
POSTSEASON_ROW_2004 = [
    "20041023", "0", "Sat", "MON", "NL", "1", "OAK", "AL", "1",
    "9", "11", "54", "N", "", "", "", "OAK01", "35035", "240",
]

STATSAPI_PAYLOAD = {
    "dates": [
        {
            "date": "2024-07-05",
            "games": [
                {
                    "gamePk": 1,
                    "gameType": "R",
                    "season": "2024",
                    "gameDate": "2024-07-05T20:10:00Z",
                    "officialDate": "2024-07-05",
                    "doubleHeader": "N",
                    "gameNumber": 1,
                    "venue": {"name": "Oakland Coliseum"},
                    "teams": {
                        "away": {"team": {"teamCode": "mon"}, "score": 4},
                        "home": {"team": {"teamCode": "oak"}, "score": 1},
                    },
                }
            ],
        }
    ]
}


@pytest.fixture
def adapter(db_session):
    return MlbAdapter(db_session)


class TestMlbImportTeams:
    @pytest.mark.asyncio
    async def test_import_teams(self, adapter, db_session, mlb_league):
        with patch.object(adapter, "_get_text", AsyncMock(return_value=TEAMS_CSV)):
            result = await adapter.import_teams()

        assert result.teams_imported == 3
        expos = db_session.query(Team).filter(Team.abbreviation == "MON").one()
        nats = db_session.query(Team).filter(Team.abbreviation == "WAS").one()
        assert expos.franchise_id == nats.franchise_id  # franchise-linked despite relocation
        assert expos.last_season == 2004
        assert nats.last_season is None  # no end date -> still active
        assert expos.city == "Montreal"
        assert expos.league_id == mlb_league.id

    @pytest.mark.asyncio
    async def test_import_teams_idempotent(self, adapter, db_session):
        with patch.object(adapter, "_get_text", AsyncMock(return_value=TEAMS_CSV)):
            await adapter.import_teams()
            result = await adapter.import_teams()
        assert result.teams_imported == 0
        assert db_session.query(Team).count() == 3


class TestMlbImportSeason:
    @pytest.mark.asyncio
    async def test_import_season(self, adapter, db_session):
        with patch.object(adapter, "_get_text", AsyncMock(return_value=TEAMS_CSV)):
            await adapter.import_teams()

        with patch.object(adapter, "_get_text", AsyncMock(return_value=PARKS_CSV)), \
             patch.object(adapter, "_get_gamelog_rows", AsyncMock(return_value=[GAMELOG_ROW_1970])):
            result = await adapter.import_season(1970)

        assert result.games_imported == 1
        game = db_session.query(Game).one()
        assert game.season == 1970
        assert game.season_type == "regular"
        assert (game.away_score, game.home_score) == (3, 2)
        assert game.source_game_id == "19700406_OAK_MON_0"
        assert game.venue.name == "Parc Jarry"
        assert game.venue.city == "Montreal"
        assert db_session.query(Venue).count() == 1


class TestMlbImportPostseason:
    @pytest.mark.asyncio
    async def test_import_postseason_filters_by_season(self, adapter, db_session):
        with patch.object(adapter, "_get_text", AsyncMock(return_value=TEAMS_CSV)):
            await adapter.import_teams()

        # Every series-type file returns both rows; only the 1973 one is in range.
        with patch.object(adapter, "_get_text", AsyncMock(return_value=PARKS_CSV)), \
             patch.object(adapter, "_get_postseason_rows",
                          AsyncMock(return_value=[POSTSEASON_ROW_1973, POSTSEASON_ROW_2004])):
            result = await adapter.import_postseason(1970, 1990)

        assert result.games_imported == 1
        assert not result.errors
        game = db_session.query(Game).one()
        assert game.season == 1973
        assert game.season_type == "postseason"
        assert game.source_game_id == "19731013_MON_OAK_0"
        assert (game.away_score, game.home_score) == (2, 3)
        assert game.overtime_flag == "11"  # 66 outs -> extra innings
        assert game.venue.name == "Oakland Coliseum"

    @pytest.mark.asyncio
    async def test_import_postseason_idempotent(self, adapter, db_session):
        with patch.object(adapter, "_get_text", AsyncMock(return_value=TEAMS_CSV)):
            await adapter.import_teams()

        with patch.object(adapter, "_get_text", AsyncMock(return_value=PARKS_CSV)), \
             patch.object(adapter, "_get_postseason_rows",
                          AsyncMock(return_value=[POSTSEASON_ROW_1973])):
            await adapter.import_postseason(1970, 1990)
            result = await adapter.import_postseason(1970, 1990)

        assert result.games_imported == 0
        assert result.games_updated == 4  # same game seen once per series-type file
        assert db_session.query(Game).count() == 1


class TestMlbSync:
    @pytest.mark.asyncio
    async def test_sync_recent_resolves_via_teamcode(self, adapter, db_session):
        with patch.object(adapter, "_get_text", AsyncMock(return_value=TEAMS_CSV)):
            await adapter.import_teams()

        with patch.object(adapter, "_fetch_schedule", AsyncMock(return_value=STATSAPI_PAYLOAD)):
            result = await adapter.sync_recent(since=date(2024, 7, 1))

        assert result.games_imported == 1
        assert not result.errors
        game = db_session.query(Game).one()
        assert game.source_game_id == "20240705_MON_OAK_0"
        assert (game.away_score, game.home_score) == (4, 1)
        assert game.venue.name == "Oakland Coliseum"
