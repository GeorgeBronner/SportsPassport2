from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from collections import defaultdict
from college_football_tracker.db.database import get_db
from college_football_tracker.models.attendance import UserGameAttendance
from college_football_tracker.models.game import Game
from college_football_tracker.models.team import Team
from college_football_tracker.models.venue import Venue
from college_football_tracker.models.user import User
from college_football_tracker.schemas.attendance import (
    AttendanceCreate,
    AttendanceUpdate,
    AttendanceResponse,
    AttendanceStats,
    BulkAttendanceRequest,
    BulkAttendanceResponse
)
from college_football_tracker.core.dependencies import get_current_user

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@router.post("/", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
def mark_game_attended(
    attendance_data: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a game as attended by the current user"""
    # Check if game exists
    game = db.query(Game).filter(Game.id == attendance_data.game_id).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found"
        )

    # Check if already marked as attended
    existing = db.query(UserGameAttendance).filter(
        UserGameAttendance.user_id == current_user.id,
        UserGameAttendance.game_id == attendance_data.game_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Game already marked as attended"
        )

    # Create attendance record
    attendance = UserGameAttendance(
        user_id=current_user.id,
        game_id=attendance_data.game_id,
        notes=attendance_data.notes
    )

    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    return attendance


@router.get("/", response_model=List[AttendanceResponse])
def list_attended_games(
    skip: int = 0,
    limit: int = 10000,  # High default limit to return all games for personal/family use
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all games attended by the current user"""
    attendances = db.query(UserGameAttendance).filter(
        UserGameAttendance.user_id == current_user.id
    ).order_by(UserGameAttendance.created_at.desc()).offset(skip).limit(limit).all()

    return attendances


@router.get("/stats", response_model=AttendanceStats)
def get_attendance_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get attendance statistics for the current user"""
    # Get all attended games with related data
    attendances = db.query(UserGameAttendance).filter(
        UserGameAttendance.user_id == current_user.id
    ).all()

    if not attendances:
        return AttendanceStats(
            total_games=0,
            unique_stadiums=0,
            unique_states=0,
            games_by_team={},
            games_by_season={},
            stadiums_visited=[],
            states_visited=[]
        )

    # Calculate statistics
    total_games = len(attendances)
    games_by_team = defaultdict(int)
    games_by_season = defaultdict(int)
    stadiums = set()
    states = set()

    for attendance in attendances:
        game = attendance.game
        games_by_season[game.season] += 1

        # Count games for both home and away teams (FBS only)
        if game.home_team and game.home_team.classification == "fbs":
            games_by_team[game.home_team.school] += 1
        if game.away_team and game.away_team.classification == "fbs":
            games_by_team[game.away_team.school] += 1

        # Track stadiums and states
        if game.venue:
            stadiums.add(game.venue.name)
            if game.venue.state:
                states.add(game.venue.state)

    return AttendanceStats(
        total_games=total_games,
        unique_stadiums=len(stadiums),
        unique_states=len(states),
        games_by_team=dict(sorted(games_by_team.items(), key=lambda x: x[1], reverse=True)),
        games_by_season=dict(sorted(games_by_season.items())),
        stadiums_visited=sorted(list(stadiums)),
        states_visited=sorted(list(states))
    )


@router.patch("/{attendance_id}", response_model=AttendanceResponse)
def update_attendance(
    attendance_id: int,
    attendance_data: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update attendance notes"""
    attendance = db.query(UserGameAttendance).filter(
        UserGameAttendance.id == attendance_id,
        UserGameAttendance.user_id == current_user.id
    ).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )

    if attendance_data.notes is not None:
        attendance.notes = attendance_data.notes

    db.commit()
    db.refresh(attendance)

    return attendance


@router.delete("/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a game from attended list"""
    attendance = db.query(UserGameAttendance).filter(
        UserGameAttendance.id == attendance_id,
        UserGameAttendance.user_id == current_user.id
    ).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )

    db.delete(attendance)
    db.commit()

    return None


@router.post("/bulk", response_model=BulkAttendanceResponse, status_code=status.HTTP_201_CREATED)
def mark_games_bulk_attended(
    bulk_request: BulkAttendanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark multiple games as attended in a single request"""
    created = 0
    skipped = 0
    errors = []

    for item in bulk_request.games:
        try:
            # Check if game exists
            game = db.query(Game).filter(Game.id == item.game_id).first()
            if not game:
                errors.append(f"Game {item.game_id} not found")
                continue

            # Check if already marked as attended
            existing = db.query(UserGameAttendance).filter(
                UserGameAttendance.user_id == current_user.id,
                UserGameAttendance.game_id == item.game_id
            ).first()

            if existing:
                skipped += 1
                continue

            # Create attendance record
            attendance = UserGameAttendance(
                user_id=current_user.id,
                game_id=item.game_id,
                notes=item.notes
            )
            db.add(attendance)
            created += 1

        except Exception as e:
            errors.append(f"Game {item.game_id}: {str(e)}")
            continue

    # Commit all at once
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save attendance records: {str(e)}"
        )

    return BulkAttendanceResponse(
        created=created,
        skipped=skipped,
        errors=errors
    )
