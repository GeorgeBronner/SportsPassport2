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


# --- Spreadspoke historical era (1970-1998) -------------------------------
# Row shapes verified against the live spreadspoke_scores.csv on 2026-08-01.

SPREADSPOKE_ROWS = [
    {
        "schedule_date": "12/23/1972", "schedule_season": "1972", "schedule_week": "Division",
        "schedule_playoff": "TRUE", "team_home": "Pittsburgh Steelers", "score_home": "13",
        "score_away": "7", "team_away": "Oakland Raiders", "stadium": "Three Rivers Stadium",
        "stadium_neutral": "FALSE",
    },
    {
        "schedule_date": "9/18/1994", "schedule_season": "1994", "schedule_week": "3",
        "schedule_playoff": "FALSE", "team_home": "Arizona Cardinals", "score_home": "17",
        "score_away": "7", "team_away": "Houston Oilers",
        # The known defect: this building did not open until 2006.
        "stadium": "University of Phoenix Stadium", "stadium_neutral": "FALSE",
    },
    {
        "schedule_date": "1/15/1978", "schedule_season": "1977", "schedule_week": "Superbowl",
        "schedule_playoff": "TRUE", "team_home": "Dallas Cowboys", "score_home": "27",
        "score_away": "10", "team_away": "Denver Broncos", "stadium": "Louisiana Superdome",
        "stadium_neutral": "TRUE",
    },
    {
        # nflverse owns 1999+; this row must be ignored no matter what is asked for.
        "schedule_date": "9/12/1999", "schedule_season": "1999", "schedule_week": "1",
        "schedule_playoff": "FALSE", "team_home": "Tennessee Titans", "score_home": "24",
        "score_away": "21", "team_away": "St. Louis Rams", "stadium": "Nissan Stadium",
        "stadium_neutral": "FALSE",
    },
]


@pytest.fixture
def spreadspoke(adapter):
    with patch.object(adapter, "_read_spreadspoke_csv", return_value=SPREADSPOKE_ROWS):
        yield adapter


class TestNflSpreadspokeEra:
    @pytest.mark.asyncio
    async def test_imports_pre_1999_games(self, spreadspoke, db_session):
        with patch.object(spreadspoke, "_get_csv", _fake_get_csv()):
            result = await spreadspoke.import_historical(1970, 1998)

        assert result.games_imported == 3  # the 1999 row belongs to nflverse
        game = db_session.query(Game).filter(
            Game.source_game_id == "spreadspoke-1972-12-23-pittsburgh-steelers-oakland-raiders"
        ).one()
        assert (game.home_score, game.away_score) == (13, 7)
        assert game.season == 1972
        assert game.season_type == "postseason"
        assert game.week is None  # named playoff round, not a numbered week
        assert game.venue.name == "Three Rivers Stadium"

    @pytest.mark.asyncio
    async def test_era_is_date_only_at_noon(self, spreadspoke, db_session):
        """The file carries no kickoff time at all (issue #8)."""
        with patch.object(spreadspoke, "_get_csv", _fake_get_csv()):
            await spreadspoke.import_historical(1970, 1998)

        game = db_session.query(Game).filter(Game.season == 1972).one()
        assert game.has_time is False
        assert game.start_date == datetime(1972, 12, 23, 12, 0)

    @pytest.mark.asyncio
    async def test_boundary_holds_in_both_directions(self, spreadspoke, db_session):
        """Spreadspoke never supplies 1999+, and nflverse is never asked for
        anything earlier, so no game can arrive from both sources."""
        with patch.object(spreadspoke, "_get_csv", _fake_get_csv()):
            await spreadspoke.import_historical(1970, 2016)

        seasons = {g.season for g in db_session.query(Game).all()}
        assert seasons == {1972, 1977, 1994, 1999, 2016}
        # The 1999 Titans/Rams game came from nflverse, not from the
        # Spreadspoke row that also describes it.
        assert db_session.query(Game).filter(Game.season == 1999).count() == 2
        assert not db_session.query(Game).filter(
            Game.source_game_id.like("spreadspoke-1999%")
        ).count()

    @pytest.mark.asyncio
    async def test_nflverse_only_range_never_reads_the_bulk_file(self, adapter, db_session):
        """A 1999+ import must not require the Kaggle download to be present."""
        def boom():
            raise AssertionError("bulk file read for a range nflverse owns")

        with patch.object(adapter, "_get_csv", _fake_get_csv()), \
             patch.object(adapter, "_read_spreadspoke_csv", side_effect=boom):
            result = await adapter.import_historical(1999, 1999)
        assert result.games_imported == 2

    @pytest.mark.asyncio
    async def test_sun_devil_stadium_override(self, spreadspoke, db_session):
        """Cardinals home games before 2006 are stamped with State Farm Stadium,
        which had not been built; they were played at Sun Devil Stadium."""
        with patch.object(spreadspoke, "_get_csv", _fake_get_csv()):
            await spreadspoke.import_historical(1970, 1998)

        game = db_session.query(Game).filter(Game.season == 1994).one()
        assert game.venue.name == "Sun Devil Stadium"
        assert game.venue.source_venue_id == "PHO99"
        assert game.venue.city == "Tempe"

    @pytest.mark.asyncio
    async def test_historical_team_gets_its_own_row(self, spreadspoke, db_session):
        """The Oilers reused HOU, which the Texans hold from 2002. Keying team
        identity on source_team_id keeps them apart."""
        with patch.object(spreadspoke, "_get_csv", _fake_get_csv()):
            await spreadspoke.import_historical(1970, 1998)

        oilers = db_session.query(Team).filter(Team.source_team_id == "HOU-OILERS").one()
        assert oilers.name == "Houston Oilers"
        assert oilers.abbreviation == "HOU"
        assert oilers.last_season == 1996
        assert oilers.franchise_id == 2100  # same franchise as the Titans

        game = db_session.query(Game).filter(Game.season == 1994).one()
        assert game.away_team_id == oilers.id

    @pytest.mark.asyncio
    async def test_shared_team_first_season_widens(self, spreadspoke, db_session):
        """A club both eras know must not still claim first_season=1999."""
        with patch.object(spreadspoke, "_get_csv", _fake_get_csv()):
            await spreadspoke.import_historical(1970, 2016)

        dallas = db_session.query(Team).filter(Team.source_team_id == "DAL").one()
        assert dallas.first_season == 1977

    @pytest.mark.asyncio
    async def test_later_nflverse_import_does_not_narrow_first_season(
        self, adapter, db_session
    ):
        """A backfill widens first_season; re-importing a range nflverse owns
        must not reset it, or the admin screen would silently undo the era.

        Uses the Rams, who appear in both eras under "LA" -- the case that
        actually exercises the clamp, since the second import does recompute
        that team from nflverse alone.
        """
        rams_1978 = {
            "schedule_date": "10/1/1978", "schedule_season": "1978", "schedule_week": "5",
            "schedule_playoff": "FALSE", "team_home": "Los Angeles Rams", "score_home": "10",
            "score_away": "3", "team_away": "Dallas Cowboys",
            "stadium": "Los Angeles Memorial Coliseum", "stadium_neutral": "FALSE",
        }
        with patch.object(adapter, "_read_spreadspoke_csv",
                          return_value=SPREADSPOKE_ROWS + [rams_1978]), \
             patch.object(adapter, "_get_csv", _fake_get_csv()):
            await adapter.import_historical(1970, 2016)
            rams = db_session.query(Team).filter(Team.source_team_id == "LA").one()
            assert rams.first_season == 1978

            # 1999+ only, so the bulk file is never consulted -- yet "LA" is in
            # the nflverse rows and gets its seasons recomputed.
            await adapter.import_historical(2016, 2016)

        db_session.expire_all()
        rams = db_session.query(Team).filter(Team.source_team_id == "LA").one()
        assert rams.first_season == 1978

    @pytest.mark.asyncio
    async def test_shared_building_reuses_the_modern_venue_row(self, spreadspoke, db_session):
        """Three Rivers Stadium is a venue nflverse also knows (PIT99). The
        historical era must land on that row, not mint a duplicate map pin."""
        row = dict(GAMES_ROWS[0], game_id="1999_01_PIT", stadium_id="PIT99",
                   stadium="Three Rivers Stadium")
        with patch.object(spreadspoke, "_get_csv", _fake_get_csv(games_rows=[row])):
            await spreadspoke.import_historical(1970, 1999)

        venues = db_session.query(Venue).filter(Venue.name == "Three Rivers Stadium").all()
        assert len(venues) == 1
        assert venues[0].source_venue_id == "PIT99"
        # The 1972 Spreadspoke game and the 1999 nflverse game are the same
        # building and must share the one row.
        historical = db_session.query(Game).filter(Game.season == 1972).one()
        modern = db_session.query(Game).filter(Game.source_game_id == "1999_01_PIT").one()
        assert historical.venue_id == modern.venue_id == venues[0].id

    @pytest.mark.asyncio
    async def test_neutral_site_with_no_attendance_or_overtime(self, spreadspoke, db_session):
        with patch.object(spreadspoke, "_get_csv", _fake_get_csv()):
            await spreadspoke.import_historical(1970, 1998)

        sb = db_session.query(Game).filter(Game.season == 1977).one()
        assert sb.neutral_site is True
        assert sb.season_type == "postseason"
        # The file has no attendance or overtime column.
        assert sb.attendance is None
        assert sb.overtime_flag is None

    @pytest.mark.asyncio
    async def test_import_is_idempotent(self, spreadspoke, db_session):
        with patch.object(spreadspoke, "_get_csv", _fake_get_csv()):
            await spreadspoke.import_historical(1970, 1998)
            result = await spreadspoke.import_historical(1970, 1998)

        assert result.games_imported == 0
        assert result.games_updated == 3
        assert db_session.query(Game).count() == 3

    @pytest.mark.asyncio
    async def test_unmapped_stadium_is_an_error_not_a_crash(self, spreadspoke, db_session):
        row = dict(SPREADSPOKE_ROWS[0], stadium="Some Unbuilt Dome")
        with patch.object(spreadspoke, "_read_spreadspoke_csv", return_value=[row]), \
             patch.object(spreadspoke, "_get_csv", _fake_get_csv()):
            result = await spreadspoke.import_historical(1970, 1998)

        assert result.games_imported == 1
        assert any("unmapped stadium" in e for e in result.errors)
        assert db_session.query(Game).one().venue_id is None

    @pytest.mark.asyncio
    async def test_missing_bulk_file_explains_how_to_get_it(
        self, adapter, tmp_path, monkeypatch
    ):
        from sports_passport.services.adapters import nfl as nfl_module

        monkeypatch.setattr(nfl_module.settings, "data_dir", str(tmp_path))
        with patch.object(adapter, "_get_csv", _fake_get_csv()), \
             pytest.raises(FileNotFoundError, match="kaggle.com"):
            await adapter.import_historical(1970, 1998)


class TestNflSpreadspokeMaps:
    """The maps are the whole correctness story for this era, so pin the
    invariants a future edit could quietly break."""

    def test_every_venue_id_exists_in_the_seed(self):
        from sports_passport.services.adapters import venue_seed
        from sports_passport.services.adapters.nfl import SPREADSPOKE_VENUE_IDS

        seed = venue_seed.nfl_stadiums()
        assert not {v for v in SPREADSPOKE_VENUE_IDS.values() if v not in seed}

    def test_historical_teams_are_all_reachable_from_the_alias_map(self):
        from sports_passport.services.adapters.nfl import (
            HISTORICAL_TEAMS, SPREADSPOKE_TEAM_ALIASES,
        )
        assert set(HISTORICAL_TEAMS) <= set(SPREADSPOKE_TEAM_ALIASES.values())
