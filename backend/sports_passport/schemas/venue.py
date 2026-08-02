
from pydantic import BaseModel, ConfigDict


class VenueBase(BaseModel):
    name: str
    city: str | None = None
    state: str | None = None
    country: str | None = None
    capacity: int | None = None


class VenueCreate(VenueBase):
    source: str
    source_venue_id: str | None = None


class VenueResponse(VenueBase):
    id: int
    latitude: float | None = None
    longitude: float | None = None

    model_config = ConfigDict(from_attributes=True)
