from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from college_football_tracker.db.database import Base


class UserGameAttendance(Base):
    __tablename__ = "user_game_attendance"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    notes = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="attended_games")
    game = relationship("Game", back_populates="user_attendances")
