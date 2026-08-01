"""Tests for the MLS adapter.

Payload shapes verified against the live American Soccer Analysis API and the
Kaggle "Major League Soccer Dataset" (josephvm) `matches.csv` on 2026-08-01.
The Kaggle rows here reproduce the real file's quirks — two date formats, a
city-suffixed venue string, thousands-separated attendance, free-text round
labels — because those are what the adapter exists to normalize.
"""
import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue
from sports_passport.services.adapters.mls import (
    MlsAdapter,
    _canonical_venue,
    _parse_kaggle_date,
    _season_type,
)

RBNY = "a2lqRX2Mr0"
NYCFC = "Vj58weDM8n"
GALAXY = "kaDQ0wRqEv"

ASA_TEAMS = [
    {"team_id": RBNY, "team_name": "New York Red Bulls", "team_abbreviation": "NYRB"},
    {"team_id": NYCFC, "team_name": "New York City FC", "team_abbreviation": "NYC"},
    {"team_id": GALAXY, "team_name": "LA Galaxy", "team_abbreviation": "LAG"},
    {"team_id": "0KPqjA456v", "team_name": "San Jose Earthquakes", "team_abbreviation": "SJE"},
    {"team_id": "Z2vQ1xlqrA", "team_name": "Sporting Kansas City", "team_abbreviation": "SKC"},
    {"team_id": "mKAqBBmqbg", "team_name": "FC Dallas", "team_abbreviation": "FCD"},
    {"team_id": "EKXMeX3Q64", "team_name": "D.C. United", "team_abbreviation": "DCU"},
    {"team_id": "19vQ2095K6", "team_name": "New England Revolution", "team_abbreviation": "NER"},
]

ASA_STADIA = [
    {
        "stadium_id": "p6qbeb850G", "stadium_name": "Red Bull Arena", "capacity": 25000,
        "city": "Harrison", "province": "New Jersey", "country": "USA",
        "latitude": 40.7367, "longitude": -74.1503,
    },
    # One of the 8 real stadia ASA lists without coordinates.
    {
        "stadium_id": "roseb0wl00", "stadium_name": "Rose Bowl", "capacity": 90000,
        "city": None, "province": None, "country": "USA",
        "latitude": None, "longitude": None,
    },
]

ASA_GAME = {
    "game_id": "asa-nyc-rbny-2015",
    "date_time_utc": "2015-05-10 23:00:00 UTC",
    "home_score": 2, "away_score": 1,
    "home_team_id": RBNY, "away_team_id": NYCFC,
    "stadium_id": "p6qbeb850G",
    "season_name": "2015", "attendance": 25217,
    "knockout_game": False, "status": "FullTime",
}


def _kaggle_row(**over):
    row = {
        "id": "", "home": "New England", "away": "San Jose",
        "date": "7/31/1996", "year": "1996", "time (utc)": "",
        "attendance": "12,871", "venue": "Foxboro Stadium",
        "league": "1996 MLS", "part_of_competition": "Regular Season",
        "game_status": "FT", "shootout": "",
        "home_score": "2", "away_score": "0",
    }
    row.update(over)
    return row


def _fake_get(games_by_season=None):
    """Stand in for MlsAdapter._get, routing on the request path."""
    games_by_season = games_by_season or {}

    async def _get(path):
        if path == "/teams":
            return ASA_TEAMS
        if path == "/stadia":
            return ASA_STADIA
        if path.startswith("/games?season_name="):
            return games_by_season.get(int(path.rsplit("=", 1)[1]), [])
        raise AssertionError(f"unexpected path {path!r}")

    return AsyncMock(side_effect=_get)


@pytest.fixture
def adapter(db_session, mls_league):
    return MlsAdapter(db_session)


class TestPureHelpers:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("BMO Field, Toronto", "BMO Field"),
            ("Foxboro Stadium (Neutral Site)", "Foxboro Stadium"),
            ("R.F.K. Stadium, Washington", "RFK Stadium"),
            ("RFK Memorial", "RFK Stadium"),
            ("Robert F. Kennedy Memorial Stadium", "RFK Stadium"),
            ("StubHub Center", "Dignity Health Sports Park"),
            ("Qwest Field, Seattle", "Lumen Field"),
            ("Sin confirmar", None),
            ("", None),
        ],
    )
    def test_venue_canonicalization(self, raw, expected):
        assert _canonical_venue(raw) == expected

    def test_neighbouring_grounds_stay_distinct(self):
        """Adjacent but genuinely different buildings must not collapse — each
        is its own place someone visited."""
        assert _canonical_venue("Mile High Stadium") != _canonical_venue(
            "Sports Authority Field at Mile High"
        )
        assert _canonical_venue("Foxboro Stadium") != _canonical_venue("Gillette Stadium")
        assert _canonical_venue("Empire Field") != _canonical_venue("BC Place, Vancouver")

    @pytest.mark.parametrize(
        "label,expected",
        [
            ("Regular Season", "regular"),
            ("Regular Season 2015", "regular"),
            (" Conference Semi-finals", "postseason"),
            ("Conference Semifinals", "postseason"),
            ("MLS Cup '96", "postseason"),
            (" Final", "postseason"),
            (" Preseason", "preseason"),
            ("", "regular"),
        ],
    )
    def test_season_type(self, label, expected):
        assert _season_type(label) == expected

    def test_both_date_formats(self):
        assert _parse_kaggle_date("7/31/1996", 1996) == datetime(1996, 7, 31)
        # The written form carries no year, so it comes from the season column.
        assert _parse_kaggle_date("Friday, March 6", 2015) == datetime(2015, 3, 6)
        assert _parse_kaggle_date("garbage", 2015) is None


class TestImportTeams:
    @pytest.mark.asyncio
    async def test_imports_asa_clubs_and_defunct_franchises(self, adapter, db_session, mls_league):
        with patch.object(adapter, "_get", _fake_get()):
            result = await adapter.import_teams()

        names = {t.name for t in db_session.query(Team).filter(Team.league_id == mls_league.id)}
        assert "New York Red Bulls" in names
        # Folded in 2001, so ASA has no row — but games at their grounds exist.
        assert {"Tampa Bay Mutiny", "Miami Fusion"} <= names
        assert result.teams_imported == len(ASA_TEAMS) + 2

        mutiny = db_session.query(Team).filter(Team.name == "Tampa Bay Mutiny").one()
        assert mutiny.last_season == 2001


class TestAsaImport:
    @pytest.mark.asyncio
    async def test_imports_game_with_utc_instant_and_venue(self, adapter, db_session):
        fake = _fake_get({2015: [ASA_GAME]})
        with patch.object(adapter, "_get", fake):
            await adapter.import_teams()
            await adapter.import_historical(2015, 2015)

        game = db_session.query(Game).filter(Game.source_game_id == "asa-nyc-rbny-2015").one()
        # ASA publishes true UTC, so it is stored verbatim with a real time.
        assert game.start_date == datetime(2015, 5, 10, 23, 0)
        assert game.has_time is True
        assert (game.home_score, game.away_score) == (2, 1)
        assert game.attendance == 25217
        assert game.season_type == "regular"
        assert game.venue.name == "Red Bull Arena"
        assert (game.venue.latitude, game.venue.longitude) == (40.7367, -74.1503)

    @pytest.mark.asyncio
    async def test_stadium_without_coordinates_falls_back_to_seed(self, adapter, db_session):
        with patch.object(adapter, "_get", _fake_get({2015: [ASA_GAME]})):
            await adapter.import_teams()
            await adapter.import_historical(2015, 2015)

        rose_bowl = db_session.query(Venue).filter(Venue.name == "Rose Bowl").one()
        assert (rose_bowl.latitude, rose_bowl.longitude) == (34.1613, -118.1677)

    @pytest.mark.asyncio
    async def test_knockout_game_is_postseason(self, adapter, db_session):
        knockout = dict(ASA_GAME, game_id="asa-knockout", knockout_game=True)
        with patch.object(adapter, "_get", _fake_get({2015: [knockout]})):
            await adapter.import_teams()
            await adapter.import_historical(2015, 2015)

        game = db_session.query(Game).filter(Game.source_game_id == "asa-knockout").one()
        assert game.season_type == "postseason"


class TestKaggleBackfill:
    async def _run(self, adapter, rows, start=1996, end=1996):
        with patch.object(adapter, "_get", _fake_get()), \
             patch.object(adapter, "_read_matches_csv", return_value=rows):
            await adapter.import_teams()
            return await adapter.import_historical(start, end)

    @pytest.mark.asyncio
    async def test_gap_era_game_is_date_only_at_noon(self, adapter, db_session):
        """The Kaggle date is the local game day, and the era's clock times are
        unreliable, so the row goes in date-only rather than implying a kickoff."""
        await self._run(adapter, [_kaggle_row()])

        game = db_session.query(Game).filter(Game.season == 1996).one()
        assert game.has_time is False
        assert game.start_date == datetime(1996, 7, 31, 12, 0)
        assert game.attendance == 12871  # thousands separator stripped
        assert game.venue.name == "Foxboro Stadium"
        assert game.venue.latitude is not None

    @pytest.mark.asyncio
    async def test_team_aliases_resolve_across_eras(self, adapter, db_session):
        """'KC Wiz' and 'Sporting Kansas City' are one franchise; both must land
        on the same team row rather than splitting the club's history."""
        await self._run(
            adapter,
            [
                _kaggle_row(home="KC Wiz", away="Dallas", date="6/1/1996", year="1996"),
                _kaggle_row(home="Sporting Kansas City", away="FC Dallas",
                            date="6/1/2011", year="2011"),
            ],
            1996,
            2012,
        )

        games = db_session.query(Game).order_by(Game.season).all()
        assert len(games) == 2
        assert games[0].home_team_id == games[1].home_team_id
        assert games[0].home_team.name == "Sporting Kansas City"

    @pytest.mark.asyncio
    async def test_defunct_franchise_game_imports(self, adapter, db_session):
        await self._run(
            adapter,
            [_kaggle_row(home="Tampa Bay", away="Miami", venue="Houlihan's Stadium")],
        )

        game = db_session.query(Game).one()
        assert game.home_team.name == "Tampa Bay Mutiny"
        assert game.away_team.name == "Miami Fusion"

    @pytest.mark.asyncio
    async def test_all_star_game_is_skipped(self, adapter, db_session):
        await self._run(
            adapter,
            [_kaggle_row(home="East All-Stars", away="West All-Stars", year="2004",
                         date="7/31/2004")],
            1996,
            2004,
        )
        assert db_session.query(Game).count() == 0

    @pytest.mark.asyncio
    async def test_shootout_recorded_and_missing_venue_tolerated(self, adapter, db_session):
        """1996-99 MLS broke ties with a shootout; 2001-03 has almost no venue
        data, and those games must still import."""
        await self._run(
            adapter,
            [_kaggle_row(shootout="4-2", home_score="1", away_score="1", venue="")],
        )

        game = db_session.query(Game).one()
        assert game.overtime_flag == "SO"
        assert game.venue_id is None

    @pytest.mark.asyncio
    async def test_venue_shared_with_asa_reuses_one_row(self, adapter, db_session):
        """RFK appears in both eras under different spellings. It must resolve to
        the single venue row ASA already owns, not a second uncoordinated one."""
        stadia = ASA_STADIA + [{
            "stadium_id": "rfk0000000", "stadium_name": "RFK Stadium", "capacity": 45000,
            "city": "Washington", "province": "D.C.", "country": "USA",
            "latitude": 38.8897, "longitude": -76.9714,
        }]

        async def _get(path):
            if path == "/teams":
                return ASA_TEAMS
            if path == "/stadia":
                return stadia
            return []

        rows = [
            _kaggle_row(home="D.C. United", away="Dallas", date="6/1/1996", year="1996",
                        venue="Robert F. Kennedy Memorial Stadium"),
            _kaggle_row(home="D.C. United", away="FC Dallas", date="6/1/2011", year="2011",
                        venue="R.F.K. Stadium, Washington"),
        ]
        with patch.object(adapter, "_get", AsyncMock(side_effect=_get)), \
             patch.object(adapter, "_read_matches_csv", return_value=rows):
            await adapter.import_teams()
            await adapter.import_historical(1996, 2012)

        assert db_session.query(Venue).filter(Venue.name == "RFK Stadium").count() == 1
        games = db_session.query(Game).all()
        assert len({g.venue_id for g in games}) == 1

    @pytest.mark.asyncio
    async def test_reimport_is_idempotent(self, adapter, db_session):
        rows = [_kaggle_row()]
        await self._run(adapter, rows)
        result = await self._run(adapter, rows)

        assert db_session.query(Game).count() == 1
        assert result.games_imported == 0
        assert result.games_updated == 1


class TestSourceBoundary:
    @pytest.mark.asyncio
    async def test_kaggle_rows_from_the_asa_era_are_ignored(self, adapter, db_session):
        """ASA is authoritative from 2013, so a Kaggle row for an ASA season must
        never be imported — otherwise the same match arrives twice under two keys."""
        rows = [
            _kaggle_row(home="LA Galaxy", away="FC Dallas", date="Friday, March 6",
                        year="2015", venue="Dignity Health Sports Park"),
            _kaggle_row(date="7/31/1996", year="1996"),
        ]
        with patch.object(adapter, "_get", _fake_get({2015: [ASA_GAME]})), \
             patch.object(adapter, "_read_matches_csv", return_value=rows):
            await adapter.import_teams()
            await adapter.import_historical(1996, 2015)

        seasons = sorted(g.season for g in db_session.query(Game).all())
        # 1996 from Kaggle, 2015 from ASA — the 2015 Kaggle row is dropped.
        assert seasons == [1996, 2015]
        asa_row = db_session.query(Game).filter(Game.season == 2015).one()
        assert asa_row.source_game_id == "asa-nyc-rbny-2015"

    @pytest.mark.asyncio
    async def test_sync_never_requests_a_pre_asa_season(self, adapter, db_session):
        fake = _fake_get()
        with patch.object(adapter, "_get", fake):
            await adapter.import_teams()
            await adapter.sync_recent(date(1999, 1, 1))

        requested = [
            int(c.args[0].rsplit("=", 1)[1])
            for c in fake.call_args_list
            if c.args[0].startswith("/games?season_name=")
        ]
        assert requested and min(requested) >= 2013
