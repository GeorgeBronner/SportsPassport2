from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from college_football_tracker.db.database import get_db
from college_football_tracker.models.team import Team
from college_football_tracker.schemas.team import TeamResponse
from college_football_tracker.core.dependencies import get_current_user
from college_football_tracker.models.user import User

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("/", response_model=List[TeamResponse])
def list_teams(
    conference: Optional[str] = None,
    search: Optional[str] = None,
    division: Optional[str] = Query("fbs", description="Filter by division (fbs, fcs, or all)"),
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all teams with optional filters (defaults to FBS teams only)"""
    query = db.query(Team)

    # Filter by division (default to FBS teams only)
    if division and division.lower() != "all":
        query = query.filter(Team.division.ilike(f"%{division}%"))

    if conference:
        query = query.filter(Team.conference.ilike(f"%{conference}%"))

    if search:
        query = query.filter(Team.school.ilike(f"%{search}%"))

    teams = query.order_by(Team.school).offset(skip).limit(limit).all()
    return teams
