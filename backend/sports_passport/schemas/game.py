from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from sports_passport.schemas.team import TeamResponse
from sports_passport.schemas.venue import VenueResponse
from sports_passport.schemas.league import LeagueResponse


class GameBase(BaseModel):
    start_date: datetime  # UTC
    has_time: bool = True
    season: int
    season_type: Optional[str] = None
    week: Optional[int] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    neutral_site: bool = False
    attendance: Optional[int] = None
    overtime_flag: Optional[str] = None


class GameCreate(GameBase):
    league_id: int
    home_team_id: int
    away_team_id: int
    venue_id: Optional[int] = None
    source: str
    source_game_id: str


class GameResponse(GameBase):
    id: int
    league: LeagueResponse
    home_team_id: int
    away_team_id: int
    venue_id: Optional[int] = None
    home_team: TeamResponse
    away_team: TeamResponse
    venue: Optional[VenueResponse] = None

    model_config = ConfigDict(from_attributes=True)


class GameListResponse(BaseModel):
    id: int
    league: LeagueResponse
    start_date: datetime  # UTC
    has_time: bool = True
    season: int
    season_type: Optional[str] = None
    week: Optional[int] = None
    home_team: TeamResponse
    away_team: TeamResponse
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    venue: Optional[VenueResponse] = None

    model_config = ConfigDict(from_attributes=True)


class SeasonInfo(BaseModel):
    """Season metadata with game count"""
    season: int
    game_count: int
