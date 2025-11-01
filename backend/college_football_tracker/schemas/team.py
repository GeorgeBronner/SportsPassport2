from pydantic import BaseModel
from typing import Optional


class TeamBase(BaseModel):
    school: str
    mascot: Optional[str] = None
    abbreviation: Optional[str] = None
    conference: Optional[str] = None
    division: Optional[str] = None


class TeamCreate(TeamBase):
    api_team_id: Optional[int] = None


class TeamResponse(TeamBase):
    id: int
    api_team_id: Optional[int] = None

    class Config:
        from_attributes = True
