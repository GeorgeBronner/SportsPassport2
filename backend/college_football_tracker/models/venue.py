from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from college_football_tracker.db.database import Base


class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    city = Column(String, index=True)
    state = Column(String, index=True)
    capacity = Column(Integer)
    api_venue_id = Column(Integer, unique=True, index=True)  # ID from CollegeFootballData API

    # Relationships
    games = relationship("Game", back_populates="venue")
