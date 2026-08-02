"""Static seed data — leagues are fixed reference rows, inserted at startup."""
from sqlalchemy.orm import Session

from sports_passport.models.league import League

LEAGUES = [
    {"code": "CFB", "name": "College Football", "sport": "football"},
    {"code": "MLB", "name": "Major League Baseball", "sport": "baseball"},
    {"code": "NFL", "name": "National Football League", "sport": "football"},
    {"code": "NBA", "name": "National Basketball Association", "sport": "basketball"},
    {"code": "NHL", "name": "National Hockey League", "sport": "hockey"},
    {"code": "CBB", "name": "College Basketball", "sport": "basketball"},
    {"code": "MLS", "name": "Major League Soccer", "sport": "soccer"},
]


def seed_leagues(db: Session) -> int:
    """Insert any missing leagues. Returns number created."""
    created = 0
    for row in LEAGUES:
        if not db.query(League).filter(League.code == row["code"]).first():
            db.add(League(**row, active=True))
            created += 1
    db.commit()
    return created
