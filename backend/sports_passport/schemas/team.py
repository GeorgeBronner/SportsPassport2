from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TeamBase(BaseModel):
    name: str
    nickname: str | None = None
    abbreviation: str | None = None
    city: str | None = None
    state: str | None = None
    conference: str | None = None
    division: str | None = None
    classification: str | None = None
    first_season: int | None = None
    last_season: int | None = None


class TeamCreate(TeamBase):
    league_id: int
    source: str
    source_team_id: str | None = None


class TeamResponse(TeamBase):
    id: int
    league_id: int
    franchise_id: int | None = None
    logo_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TeamSearchResult(TeamResponse):
    """A team in cross-league search results, with the caller's attendance count."""
    league_code: str
    attended_count: int = 0


class TeamVenueCount(BaseModel):
    """How often the caller has seen a team at one venue."""
    name: str
    city: str | None = None
    state: str | None = None
    count: int


class TeamAttendanceStats(BaseModel):
    """The caller's history with one team: record when attending, seasons, venues."""
    team_id: int
    games_attended: int
    wins: int
    losses: int
    ties: int
    games_by_season: dict[int, int]
    venues: list[TeamVenueCount]
    first_game_date: datetime | None = None
    last_game_date: datetime | None = None
