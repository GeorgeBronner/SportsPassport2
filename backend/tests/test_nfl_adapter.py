"""
Tests for the NFL adapter using mocked nflverse CSV payloads (shapes verified
against the live games.csv/teams.csv on 2026-07-11).
"""
import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue
from sports_passport.services.adapters.nfl import NflAdapter

TEAMS_ROWS = [
    {"season": "2002", "team": "STL", "nfl_team_id": "2510", "full": "St Louis Rams", "nickname": "Rams"},
    {"season": "2016", "team": "LA", "nfl_team_id": "2510", "full": "Los Angeles Rams", "nickname": "Rams"},
    {"season": "2002", "team": "TEN", "nfl_team_id": "2100", "full": "Tennessee Titans", "nickname": "Titans"},
]

GAMES_ROWS = [
    {
        "game_id": "1999_01_STL_TEN", "season": "1999", "game_type": "REG", "week": "1",
        "gameday": "1999-09-12", "gametime": "", "home_team": "TEN", "away_team": "STL",
        "home_score": "24", "away_score": "21", "location": "Home", "overtime": "0",
        "stadium_id": "TEN00", "stadium": "Adelphia Coliseum",
    },
    {
        "game_id": "2000_SB_STL_TEN", "season": "1999", "game_type": "SB", "week": "22",
        "gameday": "2000-01-30", "gametime": "", "home_team": "TEN", "away_team": "STL",
        "home_score": "16", "away_score": "23", "location": "Neutral", "overtime": "0",
        "stadium_id": "GAM01", "stadium": "Georgia Dome",
    },
    {
        "game_id": "2016_01_LA_SF", "season": "2016", "game_type": "REG", "week": "1",
        "gameday": "2016-09-12", "gametime": "20:30", "home_team": "LA", "away_team": "SF",
        "home_score": "28", "away_score": "0", "location": "Home", "overtime": "0",
        "stadium_id": "LAX00", "stadium": "Los Angeles Memorial Coliseum",
    },
]


@pytest.fixture
def adapter(db_session):
    return NflAdapter(db_session)


def _fake_get_csv(games_rows=GAMES_ROWS, teams_rows=TEAMS_ROWS):
    async def fake(url):
        if "teams.csv" in url:
            return teams_rows
        return games_rows
    return AsyncMock(side_effect=fake)


class TestNflImportTeams:
    @pytest.mark.asyncio
    async def test_import_teams(self, adapter, db_session, nfl_league):
        with patch.object(adapter, "_get_csv", _fake_get_csv()):
            result = await adapter.import_teams()

        # STL, TEN, LA, SF -> 4 distinct abbreviations across the sample games
        assert result.teams_imported == 4
        rams_old = db_session.query(Team).filter(Team.abbreviation == "STL").one()
        rams_new = db_session.query(Team).filter(Team.abbreviation == "LA").one()
        assert rams_old.franchise_id == rams_new.franchise_id == 2510
        assert rams_old.first_season == 1999
        assert rams_old.last_season == 1999
        assert rams_new.last_season is None  # appears in the latest season -> still active
        assert rams_old.league_id == nfl_league.id

    @pytest.mark.asyncio
    async def test_import_teams_idempotent(self, adapter, db_session):
        with patch.object(adapter, "_get_csv", _fake_get_csv()):
            await adapter.import_teams()
            result = await adapter.import_teams()
        assert result.teams_imported == 0
        assert db_session.query(Team).count() == 4


class TestNflImportHistorical:
    @pytest.mark.asyncio
    async def test_import_historical_filters_by_season(self, adapter, db_session):
        with patch.object(adapter, "_get_csv", _fake_get_csv()):
            result = await adapter.import_historical(1999, 1999)

        assert result.games_imported == 2  # the two 1999 rows only, not the 2016 one
        assert db_session.query(Game).count() == 2

        sb = db_session.query(Game).filter(Game.source_game_id == "2000_SB_STL_TEN").one()
        assert sb.season_type == "postseason"
        assert sb.neutral_site is True
        assert (sb.home_score, sb.away_score) == (16, 23)
        assert sb.venue.name == "Georgia Dome"
        assert db_session.query(Venue).count() == 2  # both 1999 games' venues, distinct stadiums

    @pytest.mark.asyncio
    async def test_venue_backfilled_from_seed(self, adapter, db_session):
        # KAN00 is a real nflverse stadium_id present in data/seed/nfl_stadiums.csv;
        # the fixture ids above (TEN00/GAM01/LAX00) are test-only and intentionally
        # don't match the seed, so this covers the actual lookup path.
        row = {
            "game_id": "1999_02_KAN_TEN", "season": "1999", "game_type": "REG", "week": "2",
            "gameday": "1999-09-19", "gametime": "", "home_team": "TEN", "away_team": "STL",
            "home_score": "10", "away_score": "7", "location": "Home", "overtime": "0",
            "stadium_id": "KAN00", "stadium": "Arrowhead Stadium",
        }
        with patch.object(adapter, "_get_csv", _fake_get_csv(games_rows=GAMES_ROWS + [row])):
            await adapter.import_historical(1999, 1999)

        game = db_session.query(Game).filter(Game.source_game_id == "1999_02_KAN_TEN").one()
        assert game.venue.city == "Kansas City"
        assert game.venue.state == "MO"
        assert game.venue.latitude is not None

    @pytest.mark.asyncio
    async def test_unmatched_team_recorded_as_error(self, adapter, db_session):
        # teams never imported -> every game's teams are unresolved
        with patch.object(adapter, "_get_csv", _fake_get_csv(games_rows=[GAMES_ROWS[2]])):
            result = await adapter.sync_recent(since=date(2000, 1, 1))
        assert result.games_imported == 0
        assert len(result.errors) == 1
        assert "unmatched team" in result.errors[0]


class TestNflStartDateIsUtc:
    """nflverse publishes `gametime` in US Eastern for every game regardless of
    where it is played; start_date is UTC (docs/SP3_open_issues.md #7)."""

    @pytest.mark.asyncio
    async def test_kickoff_converts_from_eastern(self, adapter, db_session):
        with patch.object(adapter, "_get_csv", _fake_get_csv()):
            await adapter.import_historical(2016, 2016)

        game = db_session.query(Game).filter(Game.source_game_id == "2016_01_LA_SF").one()
        # 8:30pm EDT on 2016-09-12 -> 00:30 UTC the next day
        assert game.start_date == datetime(2016, 9, 13, 0, 30)
        assert game.has_time is True

    @pytest.mark.asyncio
    async def test_west_coast_game_still_converts_from_eastern(self, adapter, db_session):
        """The source time is Eastern even for a game played in California, so
        converting off the venue would be three hours wrong."""
        row = dict(GAMES_ROWS[2], game_id="2016_02_LA_SF", gameday="2016-01-10", gametime="16:40")
        with patch.object(adapter, "_get_csv", _fake_get_csv(games_rows=[row])):
            await adapter.import_teams()
            await adapter.import_historical(2016, 2016)

        game = db_session.query(Game).filter(Game.source_game_id == "2016_02_LA_SF").one()
        # 4:40pm EST in January -> 21:40 UTC same day
        assert game.start_date == datetime(2016, 1, 10, 21, 40)

    @pytest.mark.asyncio
    async def test_date_only_rows_keep_their_day_at_noon(self, adapter, db_session):
        """No kickoff time means nothing to convert -- shifting the bare date
        would roll it into the previous day. Date-only rows park at noon, which
        reads as the right calendar day in every US timezone even if a consumer
        forgets to pin has_time=False to UTC."""
        with patch.object(adapter, "_get_csv", _fake_get_csv()):
            await adapter.import_historical(1999, 1999)

        game = db_session.query(Game).filter(Game.source_game_id == "1999_01_STL_TEN").one()
        assert game.has_time is False
        assert game.start_date == datetime(1999, 9, 12, 12, 0)


class TestNflSync:
    @pytest.mark.asyncio
    async def test_sync_recent_filters_by_date(self, adapter, db_session):
        with patch.object(adapter, "_get_csv", _fake_get_csv()):
            await adapter.import_teams()
            result = await adapter.sync_recent(since=date(2016, 1, 1))

        # only the 2016 game is on/after the since date
        assert result.games_imported == 1
        game = db_session.query(Game).one()
        assert game.source_game_id == "2016_01_LA_SF"
        assert game.has_time is True
