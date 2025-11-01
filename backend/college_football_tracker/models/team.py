from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from college_football_tracker.db.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    school = Column(String, nullable=False, index=True)
    mascot = Column(String)
    abbreviation = Column(String, index=True)
    conference = Column(String, index=True)
    division = Column(String)
    api_team_id = Column(Integer, unique=True, index=True)  # ID from CollegeFootballData API

    # Relationships
    home_games = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")
