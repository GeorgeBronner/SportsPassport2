from pydantic import BaseModel, ConfigDict, field_serializer
from datetime import datetime
from typing import Optional, List
from sports_passport.core.serializers import naive_utc_isoformat
from sports_passport.schemas.game import GameListResponse


class AttendanceBase(BaseModel):
    game_id: int
    notes: Optional[str] = None


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(BaseModel):
    notes: Optional[str] = None


class AttendanceResponse(BaseModel):
    id: int
    user_id: int
    game_id: int
    notes: Optional[str] = None
    created_at: datetime
    game: GameListResponse

    model_config = ConfigDict(from_attributes=True)


class AttendanceVenueCount(BaseModel):
    """Attended-game count for one venue, for maps and most-visited lists."""
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
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
    first_game_date: Optional[datetime] = None  # naive, stored as UTC — see field_serializer below
    last_game_date: Optional[datetime] = None

    @field_serializer("first_game_date", "last_game_date")
    def _serialize_game_dates(self, value: Optional[datetime]) -> Optional[str]:
        return naive_utc_isoformat(value)


class AttendanceVenuePoint(BaseModel):
    """A venue the user has attended games at, with coordinates for the map."""
    venue_id: int
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    count: int
    leagues: list[str]  # league codes seen at this venue, most games first


class AttendanceVenuesResponse(BaseModel):
    venues: list[AttendanceVenuePoint]
    games_without_venue: int  # attended games whose game row has no venue yet


class BulkAttendanceItem(BaseModel):
    """Single game attendance item for bulk operations"""
    game_id: int
    notes: Optional[str] = None


class BulkAttendanceRequest(BaseModel):
    """Request to mark multiple games as attended"""
    games: List[BulkAttendanceItem]


class BulkAttendanceResponse(BaseModel):
    """Response from bulk attendance operation"""
    created: int
    skipped: int
    errors: List[str] = []
