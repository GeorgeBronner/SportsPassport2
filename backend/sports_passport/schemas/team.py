from pydantic import BaseModel, ConfigDict
from typing import Optional


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
