from pydantic import BaseModel, ConfigDict
from typing import Optional


class TeamBase(BaseModel):
    school: str
    mascot: Optional[str] = None
    abbreviation: Optional[str] = None
    conference: Optional[str] = None
    division: Optional[str] = None
    classification: Optional[str] = None


class TeamCreate(TeamBase):
    api_team_id: Optional[int] = None


class TeamResponse(TeamBase):
    id: int
    api_team_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
