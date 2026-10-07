"""
Tests for the CFB adapter using mocked CollegeFootballData.com (CFBD) payloads.
"""
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest

from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue
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
# unfiltered /teams, absent from /teams/fbs, and carrying classification: null
# rather than a missing key.
ROCKY_MOUNTAIN = {
    "id": 2826, "school": "Rocky Mountain", "mascot": "Battlin' Bears",
    "abbreviation": None, "conference": None, "classification": None,
}
MONTANA = {
    "id": 149, "school": "Montana", "mascot": "Grizzlies",
    "abbreviation": "MONT", "conference": "Big Sky", "classification": "fcs",
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


def _fake_get(fbs_teams=None, other_teams=None, games=None, games_by_year=None,
              venues=None):
    fbs_teams = fbs_teams if fbs_teams is not None else [ALABAMA, GEORGIA]
    other_teams = other_teams if other_teams is not None else []
    games = games if games is not None else []
    games_by_year = games_by_year or {}
    venues = venues if venues is not None else []

    async def fake_get(endpoint, params=None):
        if endpoint == "/teams/fbs":
            return fbs_teams
        if endpoint == "/teams":
            # CFBD's /teams has no classification filter; it ignores one and
            # returns every school, so the fake does too.
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

    @pytest.mark.asyncio
    async def test_import_teams_keeps_cfbds_own_classification_from_one_unfiltered_pull(
        self, adapter, db_session, cfb_league
    ):
        # Regression for docs/open_issues.md #16: the adapter asked /teams for
        # classification=fcs, which CFBD ignores, and defaulted every unclassified
        # school it got back to "fcs" (1,379 "FCS" teams on prod; ~130 are real).
        get = AsyncMock(side_effect=_fake_get(other_teams=[ALABAMA, MONTANA, ROCKY_MOUNTAIN]))
        with patch.object(adapter, "_get", get):
            result = await adapter.import_teams()

        assert not result.errors
        teams_calls = [c for c in get.await_args_list if c.args[0] == "/teams"]
        assert len(teams_calls) == 1
        assert not teams_calls[0].kwargs.get("params")
        by_id = {t.source_team_id: t.classification for t in db_session.query(Team)}
        assert by_id == {"333": "fbs", "61": "fbs", "149": "fcs", "2826": "other"}


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

    @pytest.mark.asyncio
    async def test_import_season_filters_games_with_classification_not_division(
        self, adapter, cfb_league
    ):
        # CFBD's /games takes `classification`; it silently ignores `division`,
        # which the adapter sent from the scaffold on, so every nightly sync
        # pulled all NCAA divisions (~4x the payload) and stored D-II/D-III
        # games. The mocked _get can't notice an ignored filter, so pin the
        # request itself.
        get = AsyncMock(side_effect=_fake_get())
        with patch.object(adapter, "_get", get):
            await adapter.import_season(2023)

        params = next(c.kwargs["params"] for c in get.await_args_list if c.args[0] == "/games")
        assert params["classification"] == "fbs"
        assert "division" not in params


class TestCfbTimesAndVenues:
    @pytest.mark.asyncio
    async def test_tbd_kickoff_is_stored_date_only_on_its_eastern_game_day(
        self, adapter, db_session, cfb_league,
    ):
        """open_issues.md #7: CFBD sends an unscheduled kickoff as a
        midnight-Eastern placeholder (real payload shape, 2026-10-06). It must
        not be published as a real 8pm-Pacific kickoff the day before."""
        games = [
            _game(id=1, startDate="2026-10-17T04:00:00.000Z", startTimeTBD=True),
            _game(id=2, startDate="2026-11-28T05:00:00.000Z", startTimeTBD=True),
            _game(id=3, startDate="2026-10-17T23:30:00.000Z", startTimeTBD=False),
        ]
        with patch.object(adapter, "_get", side_effect=_fake_get(games=games)):
            await adapter.import_teams()
            await adapter.import_season(2026)

        by_id = {g.source_game_id: g for g in db_session.query(Game).all()}
        assert (by_id["1"].has_time, by_id["1"].start_date) == (False, datetime(2026, 10, 17, 12))
        assert (by_id["2"].has_time, by_id["2"].start_date) == (False, datetime(2026, 11, 28, 12))
        assert (by_id["3"].has_time, by_id["3"].start_date) == (True, datetime(2026, 10, 17, 23, 30))

    @pytest.mark.asyncio
    async def test_import_venues_corrects_misspelled_cities(self, adapter, db_session):
        """open_issues.md #11: CFBD's own typos, which also defeated geocoding."""
        venues = [
            {"id": 5403, "name": "Orlando City Stadium", "city": "Orlanda", "state": "FL"},
            {"id": 3798, "name": "Lambeau Field", "city": "Greenbay", "state": "WI"},
        ]
        with patch.object(adapter, "_get", side_effect=_fake_get(venues=venues)):
            await adapter.import_venues()

        cities = {v.source_venue_id: v.city for v in db_session.query(Venue).all()}
        assert cities == {"5403": "Orlando", "3798": "Green Bay"}


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
