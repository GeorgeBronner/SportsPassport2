"""
Tests for the US Eastern -> UTC conversion applied to the bulk NFL and NBA
imports (docs/SP3_open_issues.md #7). `games.start_date` is defined as UTC;
both of those sources publish Eastern.
"""
from datetime import datetime

from sports_passport.services.adapters import local_time


class TestToUtc:
    def test_converts_eastern_daylight_time(self):
        """8:30pm EDT = UTC-4, so it lands after midnight the next day."""
        assert local_time.eastern_to_utc(datetime(2016, 9, 12, 20, 30)) == datetime(2016, 9, 13, 0, 30)

    def test_converts_eastern_standard_time(self):
        """4:40pm EST = UTC-5, same calendar day in UTC."""
        assert local_time.eastern_to_utc(datetime(2016, 1, 10, 16, 40)) == datetime(2016, 1, 10, 21, 40)

    def test_respects_dst_boundary(self):
        """Same wall clock either side of the US DST switch (2024-11-03)."""
        assert local_time.eastern_to_utc(datetime(2024, 11, 2, 19, 0)) == datetime(2024, 11, 2, 23, 0)
        assert local_time.eastern_to_utc(datetime(2024, 11, 4, 19, 0)) == datetime(2024, 11, 5, 0, 0)

    def test_returns_naive_datetime(self):
        """start_date is a naive column — a tz-aware value would not round-trip."""
        assert local_time.eastern_to_utc(datetime(2024, 6, 1, 19, 0)).tzinfo is None

    def test_ambiguous_hour_takes_the_first_pass(self):
        """1:30am on the autumn repeat happens twice; fold=0 picks the earlier."""
        assert local_time.eastern_to_utc(datetime(2024, 11, 3, 1, 30)) == datetime(2024, 11, 3, 5, 30)

    def test_western_venue_still_converts_from_eastern(self):
        """A 7:00pm Pacific tip-off reaches us as 22:00 Eastern, not 19:00
        local — converting it as Pacific would be three hours out. Verified
        against ESPN for Pistons @ Warriors 2026-01-30 (03:00Z)."""
        assert local_time.eastern_to_utc(datetime(2026, 1, 30, 22, 0)) == datetime(2026, 1, 31, 3, 0)
