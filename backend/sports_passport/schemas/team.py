from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class TeamBase(BaseModel):
    name: str
    nickname: Optional[str] = None
    abbreviation: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    conference: Optional[str] = None
    division: Optional[str] = None
    classification: Optional[str] = None
    first_season: Optional[int] = None
    last_season: Optional[int] = None


class TeamCreate(TeamBase):
    league_id: int
    source: str
    source_team_id: Optional[str] = None


class TeamResponse(TeamBase):
    id: int
    league_id: int
    franchise_id: Optional[int] = None
    logo_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TeamSearchResult(TeamResponse):
    """A team in cross-league search results, with the caller's attendance count."""
    league_code: str
    attended_count: int = 0


class TeamVenueCount(BaseModel):
    """How often the caller has seen a team at one venue."""
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    count: int


class TeamAttendanceStats(BaseModel):
    """The caller's history with one team: record when attending, seasons, venues."""
    team_id: int
    games_attended: int
    wins: int
    losses: int
    ties: int
    games_by_season: dict[int, int]
    venues: list[TeamVenueCount]
    first_game_date: Optional[datetime] = None
    last_game_date: Optional[datetime] = None
