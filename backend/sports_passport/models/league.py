from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from sports_passport.db.database import Base


class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)  # 'CFB','MLB','NFL','NBA','NHL'
    name = Column(String, nullable=False)
    sport = Column(String, nullable=False)  # 'football','baseball','basketball','hockey'
    active = Column(Boolean, default=True, nullable=False)

    # Relationships
    teams = relationship("Team", back_populates="league")
    games = relationship("Game", back_populates="league")
