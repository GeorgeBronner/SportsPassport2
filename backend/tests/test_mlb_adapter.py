"""
Tests for the MLB adapter using mocked Retrosheet CSV/gamelog rows and a
mocked MLB Stats API schedule payload (shapes verified against the live
sources on 2026-07-11).
"""
import re
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue
from sports_passport.services.adapters.mlb import F_PARK_ID, STATSAPI_VENUE_PARK_IDS, MlbAdapter

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

        with patch.object(adapter, "_get_text", AsyncMock(return_value=PARKS_CSV)), \
             patch.object(adapter, "_fetch_schedule", AsyncMock(return_value=STATSAPI_PAYLOAD)):
            result = await adapter.sync_recent(since=date(2024, 7, 1))

        assert result.games_imported == 1
        assert not result.errors
        game = db_session.query(Game).one()
        assert game.source_game_id == "20240705_MON_OAK_0"
        assert (game.away_score, game.home_score) == (4, 1)
        assert game.venue.name == "Oakland Coliseum"

    @pytest.mark.asyncio
    async def test_sync_recent_bridges_venue_to_retrosheet_park_id(self, adapter, db_session):
        """A synced game at a park the historical backfill already knows must
        land on the same venue row, not a second one keyed by raw API name."""
        with patch.object(adapter, "_get_text", AsyncMock(return_value=TEAMS_CSV)):
            await adapter.import_teams()

        with patch.object(adapter, "_get_text", AsyncMock(return_value=PARKS_CSV)), \
             patch.object(adapter, "_get_gamelog_rows", AsyncMock(return_value=[GAMELOG_ROW_1970])):
            await adapter.import_season(1970)  # backfills Parc Jarry as MON01

        payload = {
            "dates": [{
                "date": "2024-07-05",
                "games": [{
                    "gamePk": 2, "gameType": "R", "season": "2024",
                    "gameDate": "2024-07-05T20:10:00Z", "officialDate": "2024-07-05",
                    "doubleHeader": "N", "gameNumber": 1,
                    "venue": {"name": "Parc Jarry"},
                    "teams": {
                        "away": {"team": {"teamCode": "oak"}, "score": 2},
                        "home": {"team": {"teamCode": "mon"}, "score": 5},
                    },
                }],
            }]
        }
        with patch.object(adapter, "_get_text", AsyncMock(return_value=PARKS_CSV)), \
             patch.object(adapter, "_fetch_schedule", AsyncMock(return_value=payload)):
            result = await adapter.sync_recent(since=date(2024, 7, 1))

        assert result.games_imported == 1
        assert db_session.query(Venue).count() == 1  # bridged, not duplicated
        venue = db_session.query(Venue).one()
        assert venue.source_venue_id == "MON01"

    @pytest.mark.asyncio
    async def test_sync_recent_reconciles_legacy_venue_row(self, adapter, db_session, mlb_league):
        """A sync from before the venue bridge existed may already have a
        venue row keyed on the raw API name; once the bridge takes over,
        games on that legacy row must be reassigned onto the canonical
        park-id row instead of being orphaned."""
        with patch.object(adapter, "_get_text", AsyncMock(return_value=TEAMS_CSV)):
            await adapter.import_teams()

        mon = db_session.query(Team).filter(Team.abbreviation == "MON").one()
        oak = db_session.query(Team).filter(Team.abbreviation == "OAK").one()
        legacy_venue = Venue(
            source="retrosheet", source_venue_id="Oakland Coliseum", name="Oakland Coliseum"
        )
        db_session.add(legacy_venue)
        db_session.flush()
        legacy_game = Game(
            source="retrosheet", source_game_id="19990401_MON_OAK_0", league_id=mlb_league.id,
            home_team_id=oak.id, away_team_id=mon.id, home_score=3, away_score=1,
            start_date=datetime(1999, 4, 1), has_time=False, season=1999, season_type="regular",
            venue_id=legacy_venue.id, neutral_site=False,
        )
        db_session.add(legacy_game)
        db_session.commit()

        with patch.object(adapter, "_get_text", AsyncMock(return_value=PARKS_CSV)), \
             patch.object(adapter, "_fetch_schedule", AsyncMock(return_value=STATSAPI_PAYLOAD)):
            result = await adapter.sync_recent(since=date(2024, 7, 1))

        assert result.games_imported == 1
        assert db_session.query(Venue).count() == 1  # legacy row merged away, not orphaned
        venue = db_session.query(Venue).one()
        assert venue.source_venue_id == "OAK01"
        db_session.refresh(legacy_game)
        assert legacy_game.venue_id == venue.id  # reassigned onto the canonical row

    @pytest.mark.asyncio
    async def test_sync_recent_bridges_by_statsapi_venue_id_when_retrosheet_name_is_stale(
        self, adapter, db_session, mlb_league,
    ):
        """Retrosheet lags naming-rights renames (parkcode.txt still says
        "Suntrust Park"), so a name match misses and sync used to mint a bare
        "Truist Park" row with no city, state or coordinates. The Stats API
        venue id survives the rename: the synced game must land on the
        backfill's ATL03 row, which keeps its location and takes the current
        name, and a legacy raw-name row from before the fix is merged away."""
        with patch.object(adapter, "_get_text", AsyncMock(return_value=TEAMS_CSV)):
            await adapter.import_teams()

        parks_csv = PARKS_CSV + 'ATL03,"Suntrust Park",,Atlanta,GA,04/14/2017,,NL,""\n'
        atl_row = list(GAMELOG_ROW_1970)
        atl_row[F_PARK_ID] = "ATL03"
        with patch.object(adapter, "_get_text", AsyncMock(return_value=parks_csv)), \
             patch.object(adapter, "_get_gamelog_rows", AsyncMock(return_value=[atl_row])):
            await adapter.import_season(1970)  # backfills ATL03 as "Suntrust Park", Atlanta GA

        canonical = db_session.query(Venue).filter(Venue.source_venue_id == "ATL03").one()
        canonical.latitude, canonical.longitude = 33.890738, -84.467616
        mon = db_session.query(Team).filter(Team.abbreviation == "MON").one()
        oak = db_session.query(Team).filter(Team.abbreviation == "OAK").one()
        legacy_venue = Venue(source="retrosheet", source_venue_id="Truist Park", name="Truist Park")
        db_session.add(legacy_venue)
        db_session.flush()
        legacy_game = Game(
            source="retrosheet", source_game_id="20240704_MON_OAK_0", league_id=mlb_league.id,
            home_team_id=oak.id, away_team_id=mon.id, home_score=3, away_score=1,
            start_date=datetime(2024, 7, 4), has_time=False, season=2024, season_type="regular",
            venue_id=legacy_venue.id, neutral_site=False,
        )
        db_session.add(legacy_game)
        db_session.commit()

        payload = {
            "dates": [{
                "date": "2024-07-05",
                "games": [{
                    "gamePk": 4, "gameType": "R", "season": "2024",
                    "gameDate": "2024-07-05T20:10:00Z", "officialDate": "2024-07-05",
                    "doubleHeader": "N", "gameNumber": 1,
                    "venue": {"id": 4705, "name": "Truist Park"},
                    "teams": {
                        "away": {"team": {"teamCode": "mon"}, "score": 2},
                        "home": {"team": {"teamCode": "oak"}, "score": 5},
                    },
                }],
            }]
        }
        with patch.object(adapter, "_get_text", AsyncMock(return_value=parks_csv)), \
             patch.object(adapter, "_fetch_schedule", AsyncMock(return_value=payload)):
            result = await adapter.sync_recent(since=date(2024, 7, 1))

        assert result.games_imported == 1
        assert not result.errors
        assert db_session.query(Venue).count() == 1  # bridged onto ATL03, legacy row merged away
        venue = db_session.query(Venue).one()
        assert venue.source_venue_id == "ATL03"
        assert venue.name == "Truist Park"  # current name wins over Retrosheet's stale one
        assert (venue.city, venue.state) == ("Atlanta", "GA")
        assert (venue.latitude, venue.longitude) == (33.890738, -84.467616)
        db_session.refresh(legacy_game)
        assert legacy_game.venue_id == venue.id
        synced = db_session.query(Game).filter(Game.source_game_id == "20240705_MON_OAK_0").one()
        assert synced.venue_id == venue.id

    def test_bridge_park_id_prefers_venue_id_then_name(self):
        by_name = {"oaklandcoliseum": "OAK01", "suntrustpark": "ATL03"}
        # id map wins even when the name would match something else
        assert MlbAdapter._bridge_park_id(4705, "Oakland Coliseum", by_name) == "ATL03"
        # unknown id falls back to the name match
        assert MlbAdapter._bridge_park_id(999999, "Oakland Coliseum", by_name) == "OAK01"
        assert MlbAdapter._bridge_park_id(None, "Oakland Coliseum", by_name) == "OAK01"
        # neither known
        assert MlbAdapter._bridge_park_id(None, "Some Brand New Ballpark", by_name) is None

    def test_statsapi_venue_park_ids_are_well_formed(self):
        """Every value must be a Retrosheet park id, or the bridge would key
        venues on garbage and the coordinate seed would never find them."""
        for statsapi_id, park_id in STATSAPI_VENUE_PARK_IDS.items():
            assert isinstance(statsapi_id, int) and statsapi_id > 0
            assert re.fullmatch(r"[A-Z]{3}\d{2}", park_id), park_id
        assert len(set(STATSAPI_VENUE_PARK_IDS.values())) == len(STATSAPI_VENUE_PARK_IDS)

    @pytest.mark.asyncio
    async def test_sync_recent_falls_back_when_no_park_match(self, adapter, db_session):
        with patch.object(adapter, "_get_text", AsyncMock(return_value=TEAMS_CSV)):
            await adapter.import_teams()

        payload = {
            "dates": [{
                "date": "2024-07-05",
                "games": [{
                    "gamePk": 3, "gameType": "R", "season": "2024",
                    "gameDate": "2024-07-05T20:10:00Z", "officialDate": "2024-07-05",
                    "doubleHeader": "N", "gameNumber": 1,
                    "venue": {"name": "Some Brand New Ballpark"},
                    "teams": {
                        "away": {"team": {"teamCode": "mon"}, "score": 2},
                        "home": {"team": {"teamCode": "oak"}, "score": 5},
                    },
                }],
            }]
        }
        with patch.object(adapter, "_get_text", AsyncMock(return_value=PARKS_CSV)), \
             patch.object(adapter, "_fetch_schedule", AsyncMock(return_value=payload)):
            result = await adapter.sync_recent(since=date(2024, 7, 1))

        assert result.games_imported == 1
        venue = db_session.query(Venue).one()
        assert venue.source_venue_id == "Some Brand New Ballpark"

    @pytest.mark.asyncio
    async def test_sync_recent_survives_retrosheet_outage(self, adapter, db_session):
        """A Retrosheet hiccup must not fail the whole sync — the venue
        bridge is an enhancement over the sync path's old behavior, not a
        prerequisite for it."""
        with patch.object(adapter, "_get_text", AsyncMock(return_value=TEAMS_CSV)):
            await adapter.import_teams()

        with patch.object(
            adapter, "_get_text",
            AsyncMock(side_effect=httpx.ConnectError("connection refused")),
        ), patch.object(adapter, "_fetch_schedule", AsyncMock(return_value=STATSAPI_PAYLOAD)):
            result = await adapter.sync_recent(since=date(2024, 7, 1))

        assert result.games_imported == 1
        assert any("parkcode.txt" in e for e in result.errors)
        venue = db_session.query(Venue).one()
        assert venue.source_venue_id == "Oakland Coliseum"  # fell back to raw name
