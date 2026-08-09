from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from sports_passport.db.database import Base

if TYPE_CHECKING:
    from sports_passport.models.game import Game
    from sports_passport.models.user import User


class UserGameAttendance(Base):
    __tablename__ = "user_game_attendance"

    # A user attends a given game once. The routers check before inserting, but
    # two concurrent requests can both pass that check — the database is what
    # actually makes it true.
    __table_args__ = (
        Index("uq_user_game_attendance", "user_id", "game_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), index=True)
    notes: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="attended_games")
    game: Mapped["Game"] = relationship("Game", back_populates="user_attendances")
