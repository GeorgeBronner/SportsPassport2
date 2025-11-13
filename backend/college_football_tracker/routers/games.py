from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from college_football_tracker.db.database import get_db
from college_football_tracker.models.game import Game
from college_football_tracker.models.team import Team
from college_football_tracker.schemas.game import GameResponse, GameListResponse, SeasonInfo
from college_football_tracker.schemas.team import TeamResponse
from college_football_tracker.core.dependencies import get_current_user
from college_football_tracker.models.user import User

router = APIRouter(prefix="/api/games", tags=["games"])


@router.get("/", response_model=List[GameListResponse])
def list_games(
    season: Optional[int] = None,
    team: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List games with optional filters"""
    query = db.query(Game)

    if season:
        query = query.filter(Game.season == season)

    if team:
        # Search by exact team school name
        team_ids = db.query(Team.id).filter(
            Team.school == team
        ).all()
        team_ids = [t[0] for t in team_ids]
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
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Search games by team name"""
    # Search teams
    team_ids = db.query(Team.id).filter(
        Team.school.ilike(f"%{q}%")
    ).all()
    team_ids = [t[0] for t in team_ids]

    # Find games with those teams
    games = db.query(Game).filter(
        or_(
            Game.home_team_id.in_(team_ids),
            Game.away_team_id.in_(team_ids)
        )
    ).order_by(Game.start_date.desc()).offset(skip).limit(limit).all()

    return games


@router.get("/seasons", response_model=List[SeasonInfo])
def list_seasons(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all available seasons with game counts"""
    seasons = db.query(
        Game.season,
        func.count(Game.id).label('game_count')
    ).group_by(Game.season).order_by(Game.season.desc()).all()

    return [
        {"season": season, "game_count": count}
        for season, count in seasons
    ]


@router.get("/count")
def count_games(
    season: Optional[int] = None,
    team: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Count games matching filters"""
    query = db.query(func.count(Game.id))

    if season:
        query = query.filter(Game.season == season)

    if team:
        # Search by exact team school name
        team_ids = db.query(Team.id).filter(
            Team.school == team
        ).all()
        team_ids = [t[0] for t in team_ids]
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
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all games for a specific team by ID"""
    # Verify team exists
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
