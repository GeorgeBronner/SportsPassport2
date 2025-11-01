from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from college_football_tracker.schemas.game import GameListResponse


class AttendanceBase(BaseModel):
    game_id: int
    notes: Optional[str] = None


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(BaseModel):
    notes: Optional[str] = None


class AttendanceResponse(BaseModel):
    id: int
    user_id: int
    game_id: int
    notes: Optional[str] = None
    created_at: datetime
    game: GameListResponse

    class Config:
        from_attributes = True


class AttendanceStats(BaseModel):
    total_games: int
    unique_stadiums: int
    unique_states: int
    games_by_team: dict[str, int]
    games_by_season: dict[int, int]
    stadiums_visited: list[str]
    states_visited: list[str]


class BulkAttendanceItem(BaseModel):
    """Single game attendance item for bulk operations"""
    game_id: int
    notes: Optional[str] = None


class BulkAttendanceRequest(BaseModel):
    """Request to mark multiple games as attended"""
    games: List[BulkAttendanceItem]


class BulkAttendanceResponse(BaseModel):
    """Response from bulk attendance operation"""
    created: int
    skipped: int
    errors: List[str] = []
