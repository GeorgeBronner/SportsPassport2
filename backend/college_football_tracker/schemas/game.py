from pydantic import BaseModel
from datetime import date
from typing import Optional
from college_football_tracker.schemas.team import TeamResponse
from college_football_tracker.schemas.venue import VenueResponse


class GameBase(BaseModel):
    game_date: date
    season: int
    week: Optional[int] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    attendance: Optional[int] = None


class GameCreate(GameBase):
    home_team_id: int
    away_team_id: int
    venue_id: Optional[int] = None
    api_game_id: Optional[int] = None


class GameResponse(GameBase):
    id: int
    home_team_id: int
    away_team_id: int
    venue_id: Optional[int] = None
    api_game_id: Optional[int] = None
    home_team: TeamResponse
    away_team: TeamResponse
    venue: Optional[VenueResponse] = None

    class Config:
        from_attributes = True


class GameListResponse(BaseModel):
    id: int
    game_date: date
    season: int
    week: Optional[int] = None
    home_team: TeamResponse
    away_team: TeamResponse
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    venue: Optional[VenueResponse] = None

    class Config:
        from_attributes = True


class SeasonInfo(BaseModel):
    """Season metadata with game count"""
    season: int
    game_count: int
