from typing import TYPE_CHECKING

from sqlalchemy import Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sports_passport.db.database import Base

if TYPE_CHECKING:
    from sports_passport.models.game import Game


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (
        UniqueConstraint("source", "source_venue_id", name="uq_venue_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    city: Mapped[str | None] = mapped_column(String, index=True)
    state: Mapped[str | None] = mapped_column(String, index=True)
    country: Mapped[str | None] = mapped_column(String, default="USA")
    capacity: Mapped[int | None] = mapped_column(Integer)
    # city-level precision is fine for the map
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String, index=True)
    source_venue_id: Mapped[str | None] = mapped_column(String, index=True)

    # Relationships
    games: Mapped[list["Game"]] = relationship("Game", back_populates="venue")
