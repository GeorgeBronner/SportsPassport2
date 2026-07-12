"""Adapter registry — maps league codes to their adapter classes.

Adding a league = writing one adapter module and registering it here
(plus a row in the leagues seed).
"""
from sqlalchemy.orm import Session

from sports_passport.services.adapters.base import LeagueAdapter, ImportResult
from sports_passport.services.adapters.cfb import CfbAdapter
from sports_passport.services.adapters.nhl import NhlAdapter
from sports_passport.services.adapters.nfl import NflAdapter
from sports_passport.services.adapters.mlb import MlbAdapter

ADAPTERS: dict[str, type[LeagueAdapter]] = {
    CfbAdapter.league_code: CfbAdapter,
    NhlAdapter.league_code: NhlAdapter,
    NflAdapter.league_code: NflAdapter,
    MlbAdapter.league_code: MlbAdapter,
}


def get_adapter(league_code: str, db: Session) -> LeagueAdapter:
    """Instantiate the adapter for a league code. Raises KeyError if unknown."""
    return ADAPTERS[league_code.upper()](db)


__all__ = ["LeagueAdapter", "ImportResult", "ADAPTERS", "get_adapter"]
