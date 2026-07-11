from pydantic import BaseModel, ConfigDict


class LeagueResponse(BaseModel):
    id: int
    code: str
    name: str
    sport: str
    active: bool

    model_config = ConfigDict(from_attributes=True)
