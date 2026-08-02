from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from sports_passport.core.serializers import naive_utc_isoformat
from sports_passport.schemas.league import LeagueResponse
from sports_passport.schemas.team import TeamResponse
from sports_passport.schemas.venue import VenueResponse


class GameBase(BaseModel):
    start_date: datetime  # naive, stored as UTC — see field_serializer below
    has_time: bool = True
    season: int
    season_type: str | None = None
    week: int | None = None
    home_score: int | None = None
    away_score: int | None = None
    neutral_site: bool = False
    attendance: int | None = None
    overtime_flag: str | None = None

    @field_serializer("start_date")
    def _serialize_start_date(self, value: datetime) -> str:
        return naive_utc_isoformat(value)


class GameCreate(GameBase):
    league_id: int
    home_team_id: int
    away_team_id: int
    venue_id: int | None = None
    source: str
    source_game_id: str


class GameResponse(GameBase):
    id: int
    league: LeagueResponse
    home_team_id: int
    away_team_id: int
    venue_id: int | None = None
    home_team: TeamResponse
    away_team: TeamResponse
    venue: VenueResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class GameListResponse(BaseModel):
    id: int
    league: LeagueResponse
    start_date: datetime  # naive, stored as UTC — see field_serializer below
    has_time: bool = True
    season: int
    season_type: str | None = None
    week: int | None = None
    home_team: TeamResponse
    away_team: TeamResponse
    home_score: int | None = None
    away_score: int | None = None
    venue: VenueResponse | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("start_date")
    def _serialize_start_date(self, value: datetime) -> str:
        return naive_utc_isoformat(value)


class SeasonInfo(BaseModel):
    """Season metadata with game count"""
    season: int
    game_count: int
