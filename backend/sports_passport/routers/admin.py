from datetime import date, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from sports_passport.db.database import get_db
from sports_passport.models.user import User
from sports_passport.models.game import Game
from sports_passport.models.team import Team
from sports_passport.models.league import League
from sports_passport.models.sync_state import SyncState
from sports_passport.schemas.user import UserResponse
from sports_passport.core.dependencies import get_current_admin_user
from sports_passport.services.adapters import get_adapter, ADAPTERS
from sports_passport.services.scheduler import (
    get_or_create_sync_state,
    run_sync_all_background,
    run_sync_for_league,
    start_sync_all,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Bounds for historical import. The floor sits below the oldest season any
# league has data for (MLB 1871 via Retrosheet, NHL 1917); the ceiling is
# "next season". Outside this window the request is a typo, and honouring it
# means an adapter grinding through decades of empty seasons — the NHL adapter
# alone sleeps 250ms per request while doing it.
EARLIEST_SEASON = 1850


def _adapter_or_404(league_code: str, db: Session):
    try:
        return get_adapter(league_code, db)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No adapter implemented for league: {league_code}. "
                   f"Available: {sorted(ADAPTERS.keys())}"
        )


@router.post("/import/{league_code}/teams")
async def import_league_teams(
    league_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Import/refresh teams for a league (Admin only)"""
    adapter = _adapter_or_404(league_code, db)
    try:
        result = await adapter.import_teams()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Team import failed: {str(e)}"
        )
    finally:
        await adapter.aclose()


@router.post("/import/{league_code}/historical")
async def import_league_historical(
    league_code: str,
    start_season: int,
    end_season: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """One-time bulk historical import for a league (Admin only)"""
    if start_season > end_season:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_season must be <= end_season"
        )
    latest_season = date.today().year + 1
    if start_season < EARLIEST_SEASON or end_season > latest_season:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Seasons must fall between {EARLIEST_SEASON} and {latest_season}"
        )
    adapter = _adapter_or_404(league_code, db)
    try:
        result = await adapter.import_historical(start_season, end_season)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Historical import failed: {str(e)}"
        )
    finally:
        await adapter.aclose()


@router.post("/sync/{league_code}")
async def sync_league(
    league_code: str,
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Incremental sync of recent games for a league (Admin only).

    Records the outcome on the league's SyncState, same as the nightly job.
    Hard adapter failures surface as errors in the result rather than a 500.
    """
    _adapter_or_404(league_code, db)  # 404 for unknown league before we touch state
    return await run_sync_for_league(db, league_code, since=date.today() - timedelta(days=days))


@router.post("/sync-all", status_code=status.HTTP_202_ACCEPTED)
def sync_all_now(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin_user)
):
    """Kick off the nightly sync on demand across every enabled league (Admin only).

    Runs in the background rather than inside this request — six leagues at up
    to 600s each could otherwise hold the connection open for close to an hour.
    Returns immediately; poll GET /status for per-league progress and results.
    """
    if not start_sync_all():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sync already running")
    background_tasks.add_task(run_sync_all_background)
    return {"status": "accepted", "detail": "Sync started; poll /status for progress"}


class SyncStateUpdate(BaseModel):
    enabled: bool


@router.patch("/sync-state/{league_code}")
def set_sync_enabled(
    league_code: str,
    body: SyncStateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Enable/disable a league in the nightly auto-sync (Admin only)."""
    league = db.query(League).filter(League.code == league_code.upper()).first()
    if league is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown league: {league_code}")
    state = get_or_create_sync_state(db, league)
    state.enabled = body.enabled
    db.commit()
    return {"league": league.code, "enabled": state.enabled}


@router.get("/status")
def data_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Per-league row counts, season coverage, and nightly-sync status (Admin only)"""
    sync_by_league_id = {s.league_id: s for s in db.query(SyncState).all()}
    rows = []
    for league in db.query(League).order_by(League.code).all():
        game_count = db.query(func.count(Game.id)).filter(Game.league_id == league.id).scalar()
        team_count = db.query(func.count(Team.id)).filter(Team.league_id == league.id).scalar()
        season_range = db.query(
            func.min(Game.season), func.max(Game.season)
        ).filter(Game.league_id == league.id).first()
        state = sync_by_league_id.get(league.id)
        rows.append({
            "league": league.code,
            "adapter_available": league.code in ADAPTERS,
            "teams": team_count,
            "games": game_count,
            "first_season": season_range[0],
            "last_season": season_range[1],
            # Nightly-sync fields (enabled defaults true until a row is created)
            "sync_enabled": state.enabled if state else True,
            "last_sync_at": state.last_run_at.isoformat() if state and state.last_run_at else None,
            "last_sync_status": state.last_status if state else None,
            "last_sync_games_imported": state.last_games_imported if state else None,
            "last_sync_games_updated": state.last_games_updated if state else None,
            "last_sync_error": state.last_error if state else None,
        })
    return rows


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
