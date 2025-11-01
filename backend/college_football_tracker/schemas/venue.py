from pydantic import BaseModel
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

    class Config:
        from_attributes = True
