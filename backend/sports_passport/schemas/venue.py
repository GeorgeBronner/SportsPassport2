from pydantic import BaseModel, ConfigDict
from typing import Optional


class VenueBase(BaseModel):
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    capacity: Optional[int] = None


class VenueCreate(VenueBase):
    source: str
    source_venue_id: Optional[str] = None


class VenueResponse(VenueBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
