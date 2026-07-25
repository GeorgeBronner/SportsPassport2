"""Shared query helpers."""

LIKE_ESCAPE = "\\"


def contains_pattern(term: str) -> str:
    """Build a `%term%` LIKE pattern with the user's own wildcards neutralised.

    SQLAlchemy parameterises the value, so this is not about injection — it's
    that `%` and `_` are wildcards inside LIKE. Searching for "A_B" should find
    a team literally named that, not "AxB". Pair with ``escape=LIKE_ESCAPE``:

        Team.name.ilike(contains_pattern(q), escape=LIKE_ESCAPE)
    """
    escaped = (
        term.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", f"{LIKE_ESCAPE}%")
        .replace("_", f"{LIKE_ESCAPE}_")
    )
    return f"%{escaped}%"
