from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sports_passport.db.database import Base


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("source", "source_team_id", name="uq_team_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)  # 'Alabama', 'New York Yankees'
    nickname = Column(String)  # 'Crimson Tide', 'Yankees'
    abbreviation = Column(String, index=True)
    city = Column(String)
    state = Column(String)
    conference = Column(String, index=True)
    division = Column(String)
    classification = Column(String, index=True)  # CFB: fbs/fcs; CBB: d1/non-d1; NULL for pro leagues
    first_season = Column(Integer)
    last_season = Column(Integer)  # NULL = still active
    # Groups relocated/renamed identities of one franchise (e.g. Expos + Nationals)
    franchise_id = Column(Integer, index=True)
    logo_url = Column(String)  # served from /logos/<league>/<id>.png; NULL = monogram fallback
    source = Column(String, nullable=False, index=True)  # 'cfbd','retrosheet','nflverse','nba_stats','nhl'
    source_team_id = Column(String, index=True)

    # Relationships
    league = relationship("League", back_populates="teams")
    home_games = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")
