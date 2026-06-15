from pydantic import BaseModel, ConfigDict
from typing import Optional


class VenueBase(BaseModel):
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    capacity: Optional[int] = None


class VenueCreate(VenueBase):
    api_venue_id: Optional[int] = None


class VenueResponse(VenueBase):
    id: int
    api_venue_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
