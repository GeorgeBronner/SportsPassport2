
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from sports_passport.core.dependencies import get_current_user
from sports_passport.db.database import get_db
from sports_passport.models.league import League
from sports_passport.models.user import User
from sports_passport.schemas.league import LeagueResponse

router = APIRouter(prefix="/api/leagues", tags=["leagues"])


@router.get("/", response_model=list[LeagueResponse])
def list_leagues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all leagues"""
    return db.query(League).order_by(League.code).all()
