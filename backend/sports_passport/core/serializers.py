from datetime import datetime, timezone
from typing import Optional


def naive_utc_isoformat(value: Optional[datetime]) -> Optional[str]:
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
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
