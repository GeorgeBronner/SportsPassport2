from datetime import UTC, datetime
from typing import overload


# A datetime in yields a str out; only a None input produces a None output.
# Spelled as overloads so callers serializing a required field don't have to
# widen their own return type to str | None to satisfy a type checker.
@overload
def naive_utc_isoformat(value: datetime) -> str: ...


@overload
def naive_utc_isoformat(value: None) -> None: ...


def naive_utc_isoformat(value: datetime | None) -> str | None:
    """Serialize a datetime for JSON, marking naive values as UTC explicitly.

    Game timestamps (start_date, first/last_game_date) are stored naive but
    are always UTC by convention. Without an explicit offset in the JSON
    payload, JS `new Date(...)` parses a date-time string as the browser's
    local time instead of UTC, corrupting the instant for any client not
    running in UTC — which then throws off the displayed calendar date for
    games whose UTC kickoff time lands after midnight.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()
