"""
Tests for the NBA adapter using mocked Games.csv rows (shape verified against
the real Kaggle "historical-nba-data-and-player-box-scores" dataset on
2026-07-11/12) and a mocked ESPN scoreboard payload (shape verified against
the live endpoint on 2026-08-01, when NBA sync moved off stats.nba.com).
"""
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

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

def _espn_event(**over):
    """ESPN scoreboard event; shape verified live against the real endpoint
    on 2026-08-01 (site.api.espn.com/.../basketball/nba/scoreboard)."""
    event = {
        "id": "401810723",
        "date": "2025-11-02T01:00Z",
        "season": {"year": 2026, "type": 2, "slug": "regular-season"},
        "competitions": [{
            "neutralSite": False,
            "status": {"type": {"state": "post", "name": "STATUS_FINAL", "completed": True}},
            "venue": {
                "id": "3742",
                "fullName": "Paycom Center",
                "address": {"city": "Oklahoma City", "state": "OK"},
            },
            "competitors": [
                {"homeAway": "home", "score": "110",
                 "team": {"id": "25", "displayName": "Oklahoma City Thunder"}},
                {"homeAway": "away", "score": "105",
                 "team": {"id": "2", "displayName": "Boston Celtics"}},
            ],
        }],
    }
    event.update(over)
    return event


def _payload(*events):
    return {"events": list(events)}


ESPN_PAYLOAD = _payload(_espn_event())

# All-Star weekend: real ESPN output, fielding non-franchise squads. The bulk
# import excludes All-Star games too, so these must be skipped, not errored.
ESPN_ALLSTAR_PAYLOAD = _payload(_espn_event(
    id="401810999",
    competitions=[{
        "neutralSite": True,
        "status": {"type": {"state": "post", "completed": True}},
        "competitors": [
            {"homeAway": "home", "score": "88", "team": {"displayName": "Team Stripes"}},
            {"homeAway": "away", "score": "84", "team": {"displayName": "Team Stars"}},
        ],
    }],
))


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
    async def test_csv_arena_reuses_the_seed_row_for_the_same_building(self, adapter, db_session):
        """Games.csv names the arena for its current season. Keying that by
        arenaId while the seed path keys by name gave the same building two
        rows, and the arenaId one carried no coordinates -- so a game landing
        on it dropped off the map and showed as a duplicate venue."""
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            await adapter.import_historical(2005, 2023)

        paycom = db_session.query(Venue).filter(Venue.name == "Paycom Center").all()
        assert len(paycom) == 1                      # not one per key style
        assert paycom[0].source_venue_id == "seed-Paycom Center"
        assert paycom[0].latitude is not None        # the seed's verified coords

        # ROW_THUNDER_2023 carries arenaId 1000123; that key must not survive
        assert not db_session.query(Venue).filter(
            Venue.source_venue_id == "1000123"
        ).count()

    @pytest.mark.asyncio
    async def test_arena_outside_the_seed_keeps_csv_location(self, adapter, db_session):
        """A building the seed doesn't describe -- neutral-site/global games --
        must still be recorded, with the CSV's city/state so it can be
        geocoded later rather than being silently coordinate-less."""
        mexico = _row(
            gameId="22300500",
            hometeamCity="Oklahoma City", hometeamName="Thunder", hometeamId=SONICS_ID,
            awayteamCity="Boston", awayteamName="Celtics", awayteamId=CELTICS_ID,
            gameDate="2023-11-09 20:00:00",
            arenaId="9001", arenaName="Arena Ciudad de Mexico",
            arenaCity="Mexico City", arenaState="",
        )
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS + [mexico]):
            await adapter.import_historical(2023, 2023)

        venue = db_session.query(Venue).filter(Venue.name == "Arena Ciudad de Mexico").one()
        assert venue.source_venue_id == "9001"       # no seed row to fold into
        assert venue.city == "Mexico City"
        # and it did NOT get mis-attributed to the home team's usual arena
        game = db_session.query(Game).filter(Game.source_game_id == "22300500").one()
        assert game.venue_id == venue.id

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


class TestNbaStartDateIsUtc:
    """The Kaggle CSV publishes tip-off in US Eastern for every game, wherever
    it is played; start_date is UTC (docs/SP3_open_issues.md #7)."""

    @pytest.mark.asyncio
    async def test_tipoff_converts_from_eastern(self, adapter, db_session):
        # 7:00pm EDT on 2023-11-01 -> 23:00 UTC the same day
        with patch.object(adapter, "_read_games_csv", return_value=[ROW_THUNDER_2023]):
            await adapter.import_historical(2023, 2023)

        game = db_session.query(Game).filter(Game.source_game_id == "22300002").one()
        assert game.start_date == datetime(2023, 11, 1, 23, 0)
        assert game.has_time is True

    @pytest.mark.asyncio
    async def test_western_arena_still_converts_from_eastern(self, adapter, db_session):
        """A 7:00pm Pacific tip-off arrives as 22:00 Eastern; converting off
        the arena's own zone would be three hours out. Matches ESPN's
        03:00Z for Pistons @ Warriors on this date."""
        row = _row(
            gameId="22500696", gameDate="2026-01-30 22:00:00",
            hometeamCity="Oklahoma City", hometeamName="Thunder", hometeamId=SONICS_ID,
            awayteamCity="Boston", awayteamName="Celtics", awayteamId=CELTICS_ID,
        )
        with patch.object(adapter, "_read_games_csv", return_value=[row]):
            await adapter.import_historical(2025, 2025)

        game = db_session.query(Game).filter(Game.source_game_id == "22500696").one()
        assert game.start_date == datetime(2026, 1, 31, 3, 0)

    @pytest.mark.asyncio
    async def test_pre_1996_placeholder_times_are_dropped(self, adapter, db_session):
        """Seasons before 1996 carry one or two placeholder clock values for the
        whole year, so the row keeps its local date -- parked date-only at noon,
        with has_time false -- rather than publishing a tip-off the source
        never had."""
        row = _row(gameId="27000001", gameDate="1970-11-01 19:00:00")
        with patch.object(adapter, "_read_games_csv", return_value=[row]):
            await adapter.import_historical(1970, 1970)

        game = db_session.query(Game).filter(Game.source_game_id == "27000001").one()
        assert game.has_time is False
        assert game.start_date == datetime(1970, 11, 1, 12, 0)

    @pytest.mark.asyncio
    async def test_international_game_converts_from_eastern_too(self, adapter, db_session):
        """The CSV reports games played abroad in Eastern like every other
        row, so no venue lookup is involved."""
        row = _row(
            gameId="22300500", gameDate="2023-11-09 20:00:00",
            arenaId="9001", arenaName="Arena Ciudad de Mexico",
            arenaCity="Mexico City", arenaState="",
        )
        with patch.object(adapter, "_read_games_csv", return_value=[row]):
            await adapter.import_historical(2023, 2023)

        game = db_session.query(Game).filter(Game.source_game_id == "22300500").one()
        assert game.start_date == datetime(2023, 11, 10, 1, 0)  # 8:00pm EST


class TestNbaSync:
    async def _sync(self, adapter, payload):
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            await adapter.import_teams()
        with patch.object(adapter, "_fetch_scoreboard", AsyncMock(return_value=payload)):
            return await adapter.sync_recent(since=date.today())

    @pytest.mark.asyncio
    async def test_sync_recent_imports_espn_event(self, adapter, db_session):
        result = await self._sync(adapter, ESPN_PAYLOAD)

        assert not result.errors
        assert result.games_imported == 1
        game = db_session.query(Game).one()
        assert game.source_game_id == "espn-401810723"
        # ESPN labels 2025-26 as year 2026; this app keys seasons by start year
        assert game.season == 2025
        assert game.season_type == "regular"
        assert (game.home_score, game.away_score) == (110, 105)
        assert game.has_time is True
        # resolves onto the Thunder (active identity), not the retired Sonics row
        thunder = db_session.query(Team).filter(Team.nickname == "Thunder").one()
        assert game.home_team_id == thunder.id

    @pytest.mark.asyncio
    async def test_sync_resolves_venue_via_seed_not_a_second_row(self, adapter, db_session):
        """Seed lookup keeps synced games on the same venue row the bulk
        import and backfill script use, so the map gets one dot per arena."""
        await self._sync(adapter, ESPN_PAYLOAD)

        game = db_session.query(Game).one()
        assert game.venue_id is not None
        venue = db_session.get(Venue, game.venue_id)
        assert venue.source_venue_id.startswith("seed-")
        assert venue.latitude is not None and venue.longitude is not None

    @pytest.mark.asyncio
    async def test_allstar_events_are_skipped_without_error(self, adapter, db_session):
        result = await self._sync(adapter, ESPN_ALLSTAR_PAYLOAD)

        assert not result.errors
        assert result.games_imported == 0
        assert db_session.query(Game).count() == 0

    @pytest.mark.asyncio
    async def test_sync_updates_the_bulk_row_instead_of_duplicating(self, adapter, db_session):
        """ESPN has no NBA gameId, so without natural-key reconciliation the
        synced game would land beside the bulk row rather than on it."""
        bulk = _row(
            gameId="22500001",
            hometeamCity="Oklahoma City", hometeamName="Thunder", hometeamId=SONICS_ID,
            awayteamCity="Boston", awayteamName="Celtics", awayteamId=CELTICS_ID,
            homeScore="1", awayScore="1",          # stale placeholder scores
            gameDate="2025-11-01 19:00:00",
        )
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS + [bulk]):
            await adapter.import_historical(2025, 2025)
        assert db_session.query(Game).count() == 1

        with patch.object(adapter, "_fetch_scoreboard", AsyncMock(return_value=ESPN_PAYLOAD)):
            result = await adapter.sync_recent(since=date.today())

        assert result.games_imported == 0
        assert result.games_updated == 1
        game = db_session.query(Game).one()          # still exactly one row
        assert game.source_game_id == "22500001"     # keeps the canonical id
        assert (game.home_score, game.away_score) == (110, 105)   # scores refreshed

    @pytest.mark.asyncio
    async def test_later_bulk_import_adopts_the_synced_row(self, adapter, db_session):
        """The other direction: sync sees a game first, then a refreshed
        Games.csv covers it. The row must be re-keyed, not duplicated."""
        await self._sync(adapter, ESPN_PAYLOAD)
        assert db_session.query(Game).one().source_game_id == "espn-401810723"

        bulk = _row(
            gameId="22500001",
            hometeamCity="Oklahoma City", hometeamName="Thunder", hometeamId=SONICS_ID,
            awayteamCity="Boston", awayteamName="Celtics", awayteamId=CELTICS_ID,
            homeScore="110", awayScore="105",
            gameDate="2025-11-01 19:00:00",
        )
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS + [bulk]):
            await adapter.import_historical(2025, 2025)

        assert db_session.query(Game).count() == 1
        assert db_session.query(Game).one().source_game_id == "22500001"

    @pytest.mark.asyncio
    async def test_back_to_back_same_matchup_stays_two_games(self, adapter, db_session):
        """The same pair meets on consecutive nights 294 times in the real
        dataset (287 exactly 24.0h apart). An earlier +/-1 day window sat on
        top of those, so syncing night 2 overwrote night 1 and the first game
        silently ceased to exist."""
        night1 = _espn_event(id="401000001", date="2025-11-02T01:00Z")
        night2 = _espn_event(id="401000002", date="2025-11-03T01:00Z")

        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            await adapter.import_teams()
        with patch.object(adapter, "_fetch_scoreboard",
                          AsyncMock(side_effect=[_payload(night1), _payload(night2)])):
            result = await adapter.sync_recent(since=date.today() - timedelta(days=1))

        assert not result.errors
        assert result.games_imported == 2
        assert db_session.query(Game).count() == 2
        assert {g.source_game_id for g in db_session.query(Game)} == {
            "espn-401000001", "espn-401000002",
        }

    @pytest.mark.asyncio
    async def test_ambiguous_match_errors_instead_of_guessing(self, adapter, db_session):
        """Two candidates inside the window means the key cannot identify the
        game. Guessing rewrites a real game's date and score -- and would drag
        any attendance record with it -- so this must surface, not proceed."""
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            await adapter.import_teams()

        thunder = db_session.query(Team).filter(Team.nickname == "Thunder").one()
        celtics = db_session.query(Team).filter(Team.nickname == "Celtics").one()
        for i, hours in enumerate((-2, 2)):
            db_session.add(Game(
                source="nba-kaggle", source_game_id=f"2250000{i}",
                league_id=thunder.league_id, home_team_id=thunder.id, away_team_id=celtics.id,
                start_date=datetime(2025, 11, 2, 1, 0) + timedelta(hours=hours),
                season=2025, season_type="regular", has_time=True, neutral_site=False,
            ))
        db_session.flush()

        with patch.object(adapter, "_fetch_scoreboard", AsyncMock(return_value=ESPN_PAYLOAD)):
            result = await adapter.sync_recent(since=date.today())

        assert result.games_imported == 0 and result.games_updated == 0
        assert any("more than one existing game" in e for e in result.errors)
        assert db_session.query(Game).count() == 2   # nothing rewritten, nothing added

    @pytest.mark.asyncio
    async def test_adoption_refuses_when_two_synced_rows_match(self, adapter, db_session):
        """Same guard on the bulk side: without it, two consecutive-night CSV
        rows adopt each other's synced row and the games swap identities."""
        # 22h apart: far enough to stay two distinct games, close enough that a
        # bulk row landing between them is within one window of both.
        night1 = _espn_event(id="401000001", date="2025-11-02T01:00Z")
        night2 = _espn_event(id="401000002", date="2025-11-02T23:00Z")
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            await adapter.import_teams()
        with patch.object(adapter, "_fetch_scoreboard",
                          AsyncMock(side_effect=[_payload(night1), _payload(night2)])):
            await adapter.sync_recent(since=date.today() - timedelta(days=1))
        assert db_session.query(Game).count() == 2

        # The CSV time is US Eastern and is converted on import -- 07:00 EST
        # is 12:00 UTC, the midpoint of the two synced rows and so inside both
        # windows. No realistic tip-off sits midway between two games 22h
        # apart, which is the point: this is the adversarial case the guard
        # exists for.
        bulk = _row(
            gameId="22500001",
            hometeamCity="Oklahoma City", hometeamName="Thunder", hometeamId=SONICS_ID,
            awayteamCity="Boston", awayteamName="Celtics", awayteamId=CELTICS_ID,
            gameDate="2025-11-02 07:00:00",
        )
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS + [bulk]):
            await adapter.import_historical(2025, 2025)

        # neither espn row was hijacked; the bulk row landed as its own game
        ids = {g.source_game_id for g in db_session.query(Game)}
        assert {"espn-401000001", "espn-401000002", "22500001"} <= ids

    @pytest.mark.asyncio
    async def test_postponed_game_is_not_written_as_a_zero_zero_final(self, adapter, db_session):
        """ESPN reports postponed games with state 'post' and score '0', so a
        state-based check would invent a 0-0 final."""
        postponed = _espn_event(competitions=[{
            "neutralSite": False,
            "status": {"type": {"state": "post", "name": "STATUS_POSTPONED",
                                "completed": False}},
            "venue": {"id": "3742", "fullName": "Paycom Center",
                      "address": {"city": "Oklahoma City", "state": "OK"}},
            "competitors": [
                {"homeAway": "home", "score": "0", "team": {"displayName": "Oklahoma City Thunder"}},
                {"homeAway": "away", "score": "0", "team": {"displayName": "Boston Celtics"}},
            ],
        }])
        await self._sync(adapter, _payload(postponed))

        game = db_session.query(Game).one()
        assert (game.home_score, game.away_score) == (None, None)

    @pytest.mark.asyncio
    async def test_sync_does_not_flatten_the_cup_final_to_regular(self, adapter, db_session):
        """ESPN reports the in-season tournament final as an ordinary
        regular-season game; the bulk import's more specific classification
        must survive a sync pass."""
        with patch.object(adapter, "_read_games_csv", return_value=ALL_ROWS):
            await adapter.import_historical(2023, 2023)
        cup = db_session.query(Game).filter(Game.source_game_id == "62300001").one()
        assert cup.season_type == "cup_final"

        espn_cup = _espn_event(
            id="401777777",
            date="2023-12-10T01:30Z",
            season={"year": 2024, "type": 2, "slug": "regular-season"},
            competitions=[{
                "neutralSite": True,
                "status": {"type": {"state": "post", "completed": True}},
                "competitors": [
                    {"homeAway": "home", "score": "123", "team": {"displayName": "Los Angeles Lakers"}},
                    {"homeAway": "away", "score": "109", "team": {"displayName": "Indiana Pacers"}},
                ],
            }],
        )
        with patch.object(adapter, "_fetch_scoreboard", AsyncMock(return_value=_payload(espn_cup))):
            await adapter.sync_recent(since=date.today())

        db_session.refresh(cup)
        assert cup.season_type == "cup_final"

    @pytest.mark.asyncio
    async def test_scheduled_game_does_not_blank_a_known_score(self, adapter, db_session):
        """A game already final in our DB must not be zeroed out by a later
        scoreboard fetch that still lists it as scheduled."""
        await self._sync(adapter, ESPN_PAYLOAD)

        scheduled = _espn_event(competitions=[{
            "neutralSite": False,
            "status": {"type": {"state": "pre", "completed": False}},
            "venue": {"id": "3742", "fullName": "Paycom Center",
                      "address": {"city": "Oklahoma City", "state": "OK"}},
            "competitors": [
                {"homeAway": "home", "score": "", "team": {"displayName": "Oklahoma City Thunder"}},
                {"homeAway": "away", "score": "", "team": {"displayName": "Boston Celtics"}},
            ],
        }])
        with patch.object(adapter, "_fetch_scoreboard", AsyncMock(return_value=_payload(scheduled))):
            await adapter.sync_recent(since=date.today())

        game = db_session.query(Game).one()
        assert (game.home_score, game.away_score) == (110, 105)
