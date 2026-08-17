from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sports_passport.db.database import Base

if TYPE_CHECKING:
    from sports_passport.models.game import Game
    from sports_passport.models.league import League


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("source", "source_team_id", name="uq_team_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), index=True)
    # 'Alabama', 'New York Yankees'
    name: Mapped[str] = mapped_column(String, index=True)
    nickname: Mapped[str | None] = mapped_column(String)  # 'Crimson Tide', 'Yankees'
    abbreviation: Mapped[str | None] = mapped_column(String, index=True)
    city: Mapped[str | None] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String)
    conference: Mapped[str | None] = mapped_column(String, index=True)
    division: Mapped[str | None] = mapped_column(String)
    # CFB: fbs/fcs; CBB: d1/non-d1; NULL for pro leagues
    classification: Mapped[str | None] = mapped_column(String, index=True)
    first_season: Mapped[int | None] = mapped_column(Integer)
    last_season: Mapped[int | None] = mapped_column(Integer)  # NULL = still active
    # Groups relocated/renamed identities of one franchise (e.g. Expos + Nationals)
    franchise_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # served from /logos/<league>/<id>.png; NULL = monogram fallback
    logo_url: Mapped[str | None] = mapped_column(String)
    # 'cfbd','retrosheet','nflverse','nba_stats','nhl'
    source: Mapped[str] = mapped_column(String, index=True)
    source_team_id: Mapped[str | None] = mapped_column(String, index=True)

    # Relationships
    league: Mapped["League"] = relationship("League", back_populates="teams")
    home_games: Mapped[list["Game"]] = relationship(
        "Game", foreign_keys="Game.home_team_id", back_populates="home_team"
    )
    away_games: Mapped[list["Game"]] = relationship(
        "Game", foreign_keys="Game.away_team_id", back_populates="away_team"
    )
