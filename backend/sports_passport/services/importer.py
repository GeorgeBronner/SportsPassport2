"""Shared upsert helpers used by all league adapters.

All upserts are idempotent, keyed on (source, source_*_id), so imports and
syncs can be re-run safely.
"""
from sqlalchemy.orm import Session

from sports_passport.models.game import Game
from sports_passport.models.league import League
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue


def get_league(db: Session, code: str) -> League:
    league = db.query(League).filter(League.code == code).first()
    if not league:
        raise ValueError(f"League {code} not seeded")
    return league


def upsert_team(
    db: Session, source: str, source_team_id: str, league_id: int, **fields
) -> tuple[Team, bool]:
    """Insert or update a team. Returns (team, created)."""
    team = db.query(Team).filter(
        Team.source == source,
        Team.source_team_id == source_team_id
    ).first()
    if team:
        for key, value in fields.items():
            if value is not None:
                setattr(team, key, value)
        return team, False
    team = Team(source=source, source_team_id=source_team_id, league_id=league_id, **fields)
    db.add(team)
    db.flush()  # assign PK so callers can reference team.id before commit
    return team, True


def upsert_venue(db: Session, source: str, source_venue_id: str, **fields) -> tuple[Venue, bool]:
    """Insert or update a venue. Returns (venue, created)."""
    venue = db.query(Venue).filter(
        Venue.source == source,
        Venue.source_venue_id == source_venue_id
    ).first()
    if venue:
        for key, value in fields.items():
            if value is not None:
                setattr(venue, key, value)
        return venue, False
    venue = Venue(source=source, source_venue_id=source_venue_id, **fields)
    db.add(venue)
    db.flush()
    return venue, True


def upsert_game(
    db: Session, source: str, source_game_id: str, league_id: int, **fields
) -> tuple[Game, bool]:
    """Insert or update a game. Returns (game, created).

    Score/venue/attendance fields are always overwritten on update (a sync run
    exists precisely to fill in final scores); identity fields are stable.
    """
    game = db.query(Game).filter(
        Game.source == source,
        Game.source_game_id == source_game_id
    ).first()
    if game:
        for key, value in fields.items():
            setattr(game, key, value)
        return game, False
    game = Game(source=source, source_game_id=source_game_id, league_id=league_id, **fields)
    db.add(game)
    db.flush()  # session runs autoflush=False; make the row visible to later upserts
    return game, True
