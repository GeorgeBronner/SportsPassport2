from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional
from sports_passport.db.database import get_db
from sports_passport.models.game import Game
from sports_passport.models.attendance import UserGameAttendance
from sports_passport.models.team import Team
from sports_passport.models.league import League
from sports_passport.schemas.game import GameResponse, GameListResponse, SeasonInfo
from sports_passport.core.dependencies import get_current_user
from sports_passport.models.user import User

router = APIRouter(prefix="/api/games", tags=["games"])


def _apply_league_filter(query, db: Session, league: Optional[str]):
    """Filter a Game query by league code (e.g. 'NFL'). 404s on unknown code."""
    if not league:
        return query
    league_row = db.query(League).filter(League.code == league.upper()).first()
    if not league_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown league: {league}"
        )
    return query.filter(Game.league_id == league_row.id)


def _team_ids_by_name(db: Session, name: str, exact: bool = True) -> list[int]:
    query = db.query(Team.id)
    if exact:
        query = query.filter(Team.name == name)
    else:
        query = query.filter(Team.name.ilike(f"%{name}%"))
    return [t[0] for t in query.all()]


@router.get("/", response_model=List[GameListResponse])
def list_games(
    league: Optional[str] = None,
    season: Optional[int] = None,
    team: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List games with optional filters"""
    query = db.query(Game)
    query = _apply_league_filter(query, db, league)

    if season:
        query = query.filter(Game.season == season)

    if team:
        team_ids = _team_ids_by_name(db, team)
        query = query.filter(
            or_(
                Game.home_team_id.in_(team_ids),
                Game.away_team_id.in_(team_ids)
            )
        )

    query = query.order_by(Game.start_date.desc())
    games = query.offset(skip).limit(limit).all()

    return games


@router.get("/search/", response_model=List[GameListResponse])
def search_games(
    q: str = Query(..., min_length=2),
    league: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Search games by team name"""
    team_ids = _team_ids_by_name(db, q, exact=False)

    query = db.query(Game).filter(
        or_(
            Game.home_team_id.in_(team_ids),
            Game.away_team_id.in_(team_ids)
        )
    )
    query = _apply_league_filter(query, db, league)

    games = query.order_by(Game.start_date.desc()).offset(skip).limit(limit).all()
    return games


@router.get("/seasons", response_model=List[SeasonInfo])
def list_seasons(
    league: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all available seasons with game counts"""
    query = db.query(
        Game.season,
        func.count(Game.id).label('game_count')
    )
    query = _apply_league_filter(query, db, league)
    seasons = query.group_by(Game.season).order_by(Game.season.desc()).all()

    return [
        {"season": season, "game_count": count}
        for season, count in seasons
    ]


@router.get("/count")
def count_games(
    league: Optional[str] = None,
    season: Optional[int] = None,
    team: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Count games matching filters"""
    query = db.query(func.count(Game.id))
    query = _apply_league_filter(query, db, league)

    if season:
        query = query.filter(Game.season == season)

    if team:
        team_ids = _team_ids_by_name(db, team)
        query = query.filter(
            or_(
                Game.home_team_id.in_(team_ids),
                Game.away_team_id.in_(team_ids)
            )
        )

    count = query.scalar()
    return {"count": count}


@router.get("/team/{team_id}", response_model=List[GameListResponse])
def list_team_games(
    team_id: int,
    season: Optional[int] = None,
    attended_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all games for a specific team by ID.

    attended_only restricts to games the caller attended — filtered in SQL,
    so the full attendance history surfaces regardless of the recency window.
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    query = db.query(Game).filter(
        or_(
            Game.home_team_id == team_id,
            Game.away_team_id == team_id
        )
    )

    if attended_only:
        query = query.join(UserGameAttendance, and_(
            UserGameAttendance.game_id == Game.id,
            UserGameAttendance.user_id == current_user.id,
        ))

    if season:
        query = query.filter(Game.season == season)

    games = query.order_by(Game.start_date.desc()).offset(skip).limit(limit).all()
    return games


@router.get("/{game_id}", response_model=GameResponse)
def get_game(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get game details by ID"""
    game = db.query(Game).filter(Game.id == game_id).first()

    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found"
        )

    return game
