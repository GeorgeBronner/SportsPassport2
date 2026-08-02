"""Convert the naive US Eastern wall-clock times that some bulk sources
publish into the UTC that `games.start_date` is defined to hold
(SP3_plan.md §3).

Two adapters need this: NFL (nflverse documents `gametime` as US Eastern)
and NBA (the Kaggle `Games.csv` publishes `gameDate` in Eastern too).
Everything else — NHL, CFB, CBB, and the MLB Stats API — already hands us a
UTC instant.

Both sources use Eastern for *every* game regardless of where it is played,
so there is no per-venue timezone lookup here and none is needed. That was
worth verifying rather than assuming: for both leagues, western venues'
tip-offs cluster exactly three hours later than eastern ones in the raw
data (NBA Pacific arenas peak at 22:00/22:30, NFL west-coast home games at
16:05/16:25 — i.e. 7:30pm and 1:25pm local, expressed in Eastern), and a
spot-check of Pistons @ Warriors 2026-01-30 against ESPN confirmed the
stored 22:00 is 10:00pm ET, not 10:00pm Pacific. See
docs/SP3_open_issues.md #7.
"""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")

# Time of day a date-only game (has_time=False) is parked at. Such a row
# carries a calendar game day and no real kickoff, so the hour is a storage
# detail — but it is not an arbitrary one.
#
# Noon rather than midnight, because midnight is only ever displayed correctly
# thanks to the frontend pinning has_time=False rows to UTC
# (utils/format.ts displayTimeZone). Any consumer that forgets that pin — a new
# component, a CSV export, a chart, a third-party reader of the API — renders
# midnight UTC as the *previous* calendar day everywhere west of Greenwich,
# which is the whole US. Noon UTC survives that mistake: it lands on the
# correct day for every offset from UTC-11 through UTC+11, so the stored
# instant is right by construction instead of right by convention.
DATE_ONLY_HOUR = 12


def eastern_to_utc(eastern: datetime) -> datetime:
    """A naive US Eastern wall clock -> the naive UTC instant we store.

    On the autumn DST repeat an hour is genuinely ambiguous; `fold=0` (the
    default) takes the first pass, which is the earlier real instant.
    """
    return eastern.replace(tzinfo=EASTERN).astimezone(UTC).replace(tzinfo=None)


def date_only(day: datetime) -> datetime:
    """The stored instant for a game we know the date of but not the time.

    Takes the calendar day off `day` and parks it at DATE_ONLY_HOUR, dropping
    whatever time-of-day component came in — for a has_time=False row that
    component is either absent or a placeholder the source never meant as a
    real kickoff. Callers must still pass the *local* game day; this does no
    timezone conversion, because there is no real time to convert.
    """
    return day.replace(hour=DATE_ONLY_HOUR, minute=0, second=0, microsecond=0)
