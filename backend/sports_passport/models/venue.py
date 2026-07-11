from sqlalchemy import Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sports_passport.db.database import Base


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (
        UniqueConstraint("source", "source_venue_id", name="uq_venue_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    city = Column(String, index=True)
    state = Column(String, index=True)
    country = Column(String, default="USA")
    capacity = Column(Integer)
    source = Column(String, nullable=False, index=True)
    source_venue_id = Column(String, index=True)

    # Relationships
    games = relationship("Game", back_populates="venue")
