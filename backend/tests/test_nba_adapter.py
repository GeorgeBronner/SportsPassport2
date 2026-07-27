"""
Tests for the NBA adapter using mocked Games.csv rows (shape verified against
the real Kaggle "historical-nba-data-and-player-box-scores" dataset on
2026-07-11/12) and a mocked stats.nba.com scoreboardv2 payload.
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, patch

from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue
from sports_passport.services.adapters.nba import NbaAdapter

SONICS_ID = "1610612760"
LAKERS_ID = "1610612747"
CELTICS_ID = "1610612738"
PACERS_ID = "1610612754"


def _row(**over):
    row = {
        "gameId": "20500001",
        "hometeamCity": "Seattle",
        "hometeamName": "SuperSonics",
        "hometeamId": SONICS_ID,
        "awayteamCity": "Los Angeles",
        "awayteamName": "Lakers",
        "awayteamId": LAKERS_ID,
        "homeScore": "100",
        "awayScore": "90",
        "gameType": "Regular Season",
        "gameDate": "2005-11-01 19:00:00",
        "attendance": "15000",
        "arenaId": "",
        "arenaName": "",
        "arenaCity": "",
        "arenaState": "",
    }
    row.update(over)
    return row


# Sonics' final identity era before relocating to OKC (franchise_id ties them together)
ROW_SONICS_2005 = _row()

# Same franchise, post-relocation identity, with real venue data (only current-era
# rows in the Kaggle CSV carry arena info)
ROW_THUNDER_2023 = _row(
    gameId="22300002",
    hometeamCity="Oklahoma City",
    hometeamName="Thunder",
    hometeamId=SONICS_ID,
    awayteamCity="Boston",
    awayteamName="Celtics",
    awayteamId=CELTICS_ID,
    homeScore="112",
    awayScore="108",
    gameDate="2023-11-01 19:00:00",
    attendance="18000",
    arenaId="1000123",
    arenaName="Paycom Center",
    arenaCity="Oklahoma City",
    arenaState="OK",
)

# In-season tournament championship final: gameId type digit "6", doesn't count
# toward any team's regular-season record (see nba.py GAME_TYPES comment)
ROW_CUP_FINAL_2023 = _row(
    gameId="62300001",
    hometeamCity="Los Angeles",
    hometeamName="Lakers",
    hometeamId=LAKERS_ID,
    awayteamCity="Indiana",
    awayteamName="Pacers",
    awayteamId=PACERS_ID,
    homeScore="123",
    awayScore="109",
    gameType="NBA Cup",
    gameDate="2023-12-09 20:30:00",
    attendance="17500",
    arenaId="1000200",
    arenaName="T-Mobile Arena",
    arenaCity="Las Vegas",
    arenaState="NV",
)

ALL_ROWS = [ROW_SONICS_2005, ROW_THUNDER_2023, ROW_CUP_FINAL_2023]

SCOREBOARD_PAYLOAD = {
    "resultSets": [
        {
            "name": "GameHeader",
            "headers": ["GAME_ID", "GAME_DATE_EST", "HOME_TEAM_ID", "VISITOR_TEAM_ID"],
            "rowSet": [["0022300500", "2023-11-15T00:00:00", int(SONICS_ID), int(CELTICS_ID)]],
        },
        {
            "name": "LineScore",
            "headers": ["GAME_ID", "TEAM_ID", "PTS"],
            "rowSet": [
                ["0022300500", int(SONICS_ID), 110],
                ["0022300500", int(CELTICS_ID), 105],
            ],
        },
    ]
}


@pytest.fixture
def adapter(db_session):
    return NbaAdapter(db_session)


class TestNbaImportTeams:
    @pytest.mark.asyncio
    async def test_import_teams(self, adapter, db_session, nba_league):
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            result = await adapter.import_teams()

        # Sonics, Thunder, Lakers, Celtics, Pacers
        assert result.teams_imported == 5
        sonics = db_session.query(Team).filter(Team.nickname == "SuperSonics").one()
        thunder = db_session.query(Team).filter(Team.nickname == "Thunder").one()
        assert sonics.franchise_id == thunder.franchise_id == int(SONICS_ID)
        assert sonics.last_season == 2005  # superseded by the Thunder identity
        assert thunder.last_season is None  # current identity, still active
        assert sonics.league_id == nba_league.id

    @pytest.mark.asyncio
    async def test_import_teams_idempotent(self, adapter, db_session):
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            await adapter.import_teams()
            result = await adapter.import_teams()
        assert result.teams_imported == 0
        assert db_session.query(Team).count() == 5


class TestNbaImportHistorical:
    @pytest.mark.asyncio
    async def test_import_historical(self, adapter, db_session):
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            result = await adapter.import_historical(2005, 2023)

        assert result.games_imported == 3
        assert not result.errors

        games_by_id = {g.source_game_id: g for g in db_session.query(Game).all()}
        assert games_by_id["20500001"].season == 2005
        assert games_by_id["22300002"].season == 2023

        # the fix under test: the Cup final must not be folded into "regular"
        # (it doesn't count toward either team's record)
        regular_games = [g for g in games_by_id.values() if g.season_type == "regular"]
        cup_games = [g for g in games_by_id.values() if g.season_type == "cup_final"]
        assert len(regular_games) == 2
        assert len(cup_games) == 1
        assert cup_games[0].source_game_id == "62300001"
        assert cup_games[0].season == 2023

    @pytest.mark.asyncio
    async def test_import_historical_venue_falls_back_to_seed(self, adapter, db_session):
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            await adapter.import_historical(2005, 2023)

        # 2005 row carries no arena data at all -> resolved via data/seed/nba_arenas.csv
        # (SuperSonics/Thunder franchise id 1610612760, season 2005 -> KeyArena, Seattle)
        sonics_game = db_session.query(Game).filter(Game.source_game_id == "20500001").one()
        thunder_game = db_session.query(Game).filter(Game.source_game_id == "22300002").one()
        assert sonics_game.venue.name == "KeyArena"
        assert sonics_game.venue.city == "Seattle"
        assert thunder_game.venue.name == "Paycom Center"
        assert thunder_game.venue.city == "Oklahoma City"
        assert db_session.query(Venue).count() == 3  # KeyArena + Paycom Center + T-Mobile Arena

    @pytest.mark.asyncio
    async def test_import_historical_venue_none_before_seed_coverage(self, adapter, db_session):
        # data/seed/nba_arenas.csv only covers 1990-present; an older row with no
        # arena data has nothing to fall back to and stays venue_id = NULL.
        row = _row(gameId="27000001", gameDate="1970-11-01 19:00:00")
        with patch.object(adapter, "_read_games_csv", return_value=[row]):
            await adapter.import_historical(1970, 1970)

        game = db_session.query(Game).filter(Game.source_game_id == "27000001").one()
        assert game.venue_id is None
        assert db_session.query(Venue).count() == 0

    @pytest.mark.asyncio
    async def test_import_historical_season_range_filter(self, adapter, db_session):
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            result = await adapter.import_historical(2023, 2023)

        assert result.games_imported == 2  # Thunder game + Cup final only
        assert db_session.query(Game).filter(Game.season == 2005).count() == 0


class TestNbaSync:
    @pytest.mark.asyncio
    async def test_sync_recent_resolves_active_identity_and_kaggle_id(self, adapter, db_session):
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            await adapter.import_teams()

        with patch.object(adapter, "_fetch_scoreboard", AsyncMock(return_value=SCOREBOARD_PAYLOAD)):
            result = await adapter.sync_recent(since=date.today())

        assert not result.errors
        assert result.games_imported == 1
        game = db_session.query(Game).one()
        # 10-char scoreboardv2 GAME_ID ("00" + 8-char kaggle id) must be
        # normalized to the same id form the bulk import uses
        assert game.source_game_id == "22300500"
        assert game.season == 2023
        assert (game.home_score, game.away_score) == (110, 105)
        # resolves onto the Thunder (active identity), not the retired Sonics row
        thunder = db_session.query(Team).filter(Team.nickname == "Thunder").one()
        assert game.home_team_id == thunder.id
