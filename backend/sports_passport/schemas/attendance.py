from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from sports_passport.core.serializers import naive_utc_isoformat
from sports_passport.schemas.game import GameListResponse


class AttendanceBase(BaseModel):
    game_id: int
    notes: str | None = None


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(BaseModel):
    notes: str | None = None


class AttendanceResponse(BaseModel):
    id: int
    user_id: int
    game_id: int
    notes: str | None = None
    created_at: datetime
    game: GameListResponse

    model_config = ConfigDict(from_attributes=True)


class AttendanceVenueCount(BaseModel):
    """Attended-game count for one venue, for maps and most-visited lists."""
    name: str
    city: str | None = None
    state: str | None = None
    count: int


class AttendanceStats(BaseModel):
    total_games: int
    unique_stadiums: int
    unique_states: int
    games_by_league: dict[str, int] = {}
    games_by_team: dict[str, int]
    games_by_season: dict[int, int]
    stadiums_visited: list[str]
    states_visited: list[str]
    games_by_state: dict[str, int] = {}
    venues: list[AttendanceVenueCount] = []
    first_game_date: datetime | None = None  # naive, stored as UTC — see field_serializer below
    last_game_date: datetime | None = None

    @field_serializer("first_game_date", "last_game_date")
    def _serialize_game_dates(self, value: datetime | None) -> str | None:
        return naive_utc_isoformat(value)


class AttendanceVenuePoint(BaseModel):
    """A venue the user has attended games at, with coordinates for the map."""
    venue_id: int
    name: str
    city: str | None = None
    state: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    count: int
    leagues: list[str]  # league codes seen at this venue, most games first


class AttendanceVenuesResponse(BaseModel):
    venues: list[AttendanceVenuePoint]
    games_without_venue: int  # attended games whose game row has no venue yet


class BulkAttendanceItem(BaseModel):
    """Single game attendance item for bulk operations"""
    game_id: int
    notes: str | None = None


class BulkAttendanceRequest(BaseModel):
    """Request to mark multiple games as attended.

    Capped so an oversized payload is rejected during parsing rather than
    turning into an unbounded row-by-row loop; a lifetime of attendance is a
    few thousand games, and imports can be split across requests.
    """
    games: list[BulkAttendanceItem] = Field(..., max_length=5000)


class BulkAttendanceResponse(BaseModel):
    """Response from bulk attendance operation"""
    created: int
    skipped: int
    errors: list[str] = []
