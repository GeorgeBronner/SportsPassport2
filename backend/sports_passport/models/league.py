from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sports_passport.db.database import Base

if TYPE_CHECKING:
    from sports_passport.models.game import Game
    from sports_passport.models.team import Team


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # 'CFB','MLB','NFL','NBA','NHL'
    code: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    # 'football','baseball','basketball','hockey'
    sport: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    teams: Mapped[list["Team"]] = relationship("Team", back_populates="league")
    games: Mapped[list["Game"]] = relationship("Game", back_populates="league")
