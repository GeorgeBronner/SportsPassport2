from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from college_football_tracker.db.database import Base


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    home_score = Column(Integer)
    away_score = Column(Integer)
    start_date = Column(DateTime, nullable=False, index=True)  # UTC datetime from API
    season = Column(Integer, nullable=False, index=True)
    season_type = Column(String, index=True)  # 'regular' or 'postseason'
    week = Column(Integer, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), index=True)
    attendance = Column(Integer)
    api_game_id = Column(Integer, unique=True, index=True)  # ID from CollegeFootballData API

    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    venue = relationship("Venue", back_populates="games")
    user_attendances = relationship("UserGameAttendance", back_populates="game", cascade="all, delete-orphan")
