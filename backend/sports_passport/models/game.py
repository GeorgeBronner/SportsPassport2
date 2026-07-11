from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sports_passport.db.database import Base


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("source", "source_game_id", name="uq_game_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    home_score = Column(Integer)
    away_score = Column(Integer)
    start_date = Column(DateTime, nullable=False, index=True)  # UTC
    has_time = Column(Boolean, default=True, nullable=False)  # False = date-only (old bulk data)
    season = Column(Integer, nullable=False, index=True)
    season_type = Column(String, index=True)  # 'regular', 'postseason', 'preseason'
    week = Column(Integer, index=True)  # NFL/CFB only
    venue_id = Column(Integer, ForeignKey("venues.id"), index=True)
    neutral_site = Column(Boolean, default=False, nullable=False)
    attendance = Column(Integer)
    overtime_flag = Column(String)  # 'OT','SO' (NHL), '12' innings (MLB), etc.
    source = Column(String, nullable=False, index=True)
    source_game_id = Column(String, nullable=False, index=True)

    # Relationships
    league = relationship("League", back_populates="games")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    venue = relationship("Venue", back_populates="games")
    user_attendances = relationship("UserGameAttendance", back_populates="game", cascade="all, delete-orphan")
