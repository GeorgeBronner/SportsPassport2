from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from sports_passport.db.database import get_db
from sports_passport.models.team import Team
from sports_passport.models.league import League
from sports_passport.schemas.team import TeamResponse
from sports_passport.core.dependencies import get_current_user
from sports_passport.models.user import User

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("/", response_model=List[TeamResponse])
def list_teams(
    league: Optional[str] = None,
    conference: Optional[str] = None,
    search: Optional[str] = None,
    classification: Optional[str] = None,
    franchise_id: Optional[int] = None,
    active_only: bool = False,
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all teams with optional filters"""
    query = db.query(Team)

    if league:
        league_row = db.query(League).filter(League.code == league.upper()).first()
        if not league_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown league: {league}"
            )
        query = query.filter(Team.league_id == league_row.id)

    # CFB-specific fbs/fcs filter; pass 'all' or omit for everything
    if classification and classification.lower() != "all":
        query = query.filter(Team.classification.ilike(f"%{classification}%"))

    if conference:
        query = query.filter(Team.conference.ilike(f"%{conference}%"))

    if search:
        query = query.filter(Team.name.ilike(f"%{search}%"))

    if franchise_id is not None:
        query = query.filter(Team.franchise_id == franchise_id)

    if active_only:
        query = query.filter(Team.last_season.is_(None))

    teams = query.order_by(Team.name).offset(skip).limit(limit).all()
    return teams


@router.get("/{team_id}", response_model=TeamResponse)
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single team by ID"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    return team
