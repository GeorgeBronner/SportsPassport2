from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sports_passport.db.database import Base

if TYPE_CHECKING:
    from sports_passport.models.attendance import UserGameAttendance
    from sports_passport.models.league import League
    from sports_passport.models.team import Team
    from sports_passport.models.venue import Venue


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("source", "source_game_id", name="uq_game_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), index=True)
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), index=True)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), index=True)
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC
    # False = date-only (old bulk data)
    has_time: Mapped[bool] = mapped_column(Boolean, default=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    # 'regular', 'postseason', 'preseason'
    season_type: Mapped[str | None] = mapped_column(String, index=True)
    week: Mapped[int | None] = mapped_column(Integer, index=True)  # NFL/CFB only
    venue_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("venues.id"), index=True)
    neutral_site: Mapped[bool] = mapped_column(Boolean, default=False)
    attendance: Mapped[int | None] = mapped_column(Integer)
    # 'OT','SO' (NHL), '12' innings (MLB), etc.
    overtime_flag: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, index=True)
    source_game_id: Mapped[str] = mapped_column(String, index=True)

    # Relationships
    league: Mapped["League"] = relationship("League", back_populates="games")
    home_team: Mapped["Team"] = relationship(
        "Team", foreign_keys=[home_team_id], back_populates="home_games"
    )
    away_team: Mapped["Team"] = relationship(
        "Team", foreign_keys=[away_team_id], back_populates="away_games"
    )
    venue: Mapped["Venue | None"] = relationship("Venue", back_populates="games")
    user_attendances: Mapped[list["UserGameAttendance"]] = relationship(
        "UserGameAttendance", back_populates="game", cascade="all, delete-orphan"
    )
