from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from college_football_tracker.db.database import get_db
from college_football_tracker.models.user import User
from college_football_tracker.schemas.user import UserResponse
from college_football_tracker.core.dependencies import get_current_admin_user
from college_football_tracker.services.cfb_api import CollegeFootballDataService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/refresh-data")
async def refresh_game_data(
    season: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Refresh game data from CollegeFootballData.com API (Admin only)"""
    service = CollegeFootballDataService(db)

    try:
        result = await service.import_season_data(season)
        return {
            "message": f"Successfully imported data for season {season}",
            "stats": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import data: {str(e)}"
        )


@router.get("/users", response_model=List[UserResponse])
def list_all_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """List all users (Admin only)"""
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.post("/users/{user_id}/promote")
def promote_user_to_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Promote a user to admin (Admin only)"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already an admin"
        )

    user.is_admin = True
    db.commit()
    db.refresh(user)

    return {"message": f"User {user.email} promoted to admin"}


@router.post("/users/{user_id}/demote")
def demote_user_from_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Demote a user from admin (Admin only)"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not an admin"
        )

    # Prevent self-demotion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote yourself"
        )

    user.is_admin = False
    db.commit()
    db.refresh(user)

    return {"message": f"User {user.email} demoted from admin"}
