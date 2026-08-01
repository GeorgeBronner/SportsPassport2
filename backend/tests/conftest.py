"""
Pytest configuration and fixtures for testing.
"""
import os

# Keep the nightly-sync scheduler from starting during TestClient lifespan.
os.environ["SCHEDULER_ENABLED"] = "false"
# The limiter's storage is process-wide, so the suite's many logins would trip
# the login limit and fail unrelated tests. TestRateLimiting re-enables it.
os.environ["RATE_LIMIT_ENABLED"] = "false"
# A developer's .env supplies a real DSN, so without this every run reports the
# suite's deliberately-raised exceptions to the production project, tagged with
# whatever SHA happens to be checked out.
os.environ["SENTRY_DSN"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, date

from sports_passport.main import app
from sports_passport.db.database import Base, get_db
from sports_passport.db.seed import seed_leagues
from sports_passport.models.user import User
from sports_passport.models.league import League
from sports_passport.models.team import Team
from sports_passport.models.venue import Venue
from sports_passport.models.game import Game
from sports_passport.models.attendance import UserGameAttendance
from sports_passport.core.security import get_password_hash


# Test database setup - using in-memory SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test, with leagues seeded."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    seed_leagues(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    """Create a test client with dependency injection."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # BackgroundTasks (e.g. the admin "run now" sync) don't go through get_db —
    # like the nightly scheduler job, they open their own SessionLocal. Point
    # that at the test engine too, or a background job would touch the real
    # dev database file instead of this test's in-memory one.
    monkeypatch.setattr("sports_passport.services.scheduler.SessionLocal", TestingSessionLocal)
    # Same for the lifespan's league seeding, which TestClient triggers on
    # entry. Without this it would seed the real dev database — and fail
    # outright wherever one doesn't exist yet (fresh clone, CI).
    monkeypatch.setattr("sports_passport.main.SessionLocal", TestingSessionLocal)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def cfb_league(db_session):
    return db_session.query(League).filter(League.code == "CFB").first()


@pytest.fixture
def nhl_league(db_session):
    return db_session.query(League).filter(League.code == "NHL").first()


@pytest.fixture
def nfl_league(db_session):
    return db_session.query(League).filter(League.code == "NFL").first()


@pytest.fixture
def mlb_league(db_session):
    return db_session.query(League).filter(League.code == "MLB").first()


@pytest.fixture
def nba_league(db_session):
    return db_session.query(League).filter(League.code == "NBA").first()


@pytest.fixture
def cbb_league(db_session):
    return db_session.query(League).filter(League.code == "CBB").first()


@pytest.fixture
def mls_league(db_session):
    return db_session.query(League).filter(League.code == "MLS").first()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        full_name="Test User",
        password_hash=get_password_hash("testpassword123"),
        is_admin=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_admin(db_session):
    """Create a test admin user."""
    admin = User(
        email="admin@example.com",
        full_name="Admin User",
        password_hash=get_password_hash("adminpassword123"),
        is_admin=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def user_token(client, test_user):
    """Get an authentication token for test user."""
    response = client.post(
        "/api/auth/login",
        data={
            "username": test_user.email,
            "password": "testpassword123"
        }
    )
    return response.json()["access_token"]


@pytest.fixture
def admin_token(client, test_admin):
    """Get an authentication token for admin user."""
    response = client.post(
        "/api/auth/login",
        data={
            "username": test_admin.email,
            "password": "adminpassword123"
        }
    )
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(user_token):
    """Get authorization headers for test user."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def admin_headers(admin_token):
    """Get authorization headers for admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def sample_teams(db_session, cfb_league):
    """Create sample CFB teams for testing."""
    teams = [
        Team(
            league_id=cfb_league.id,
            source="cfbd",
            source_team_id="1",
            name="Alabama",
            nickname="Crimson Tide",
            abbreviation="ALA",
            conference="SEC",
            division="West",
            classification="fbs"
        ),
        Team(
            league_id=cfb_league.id,
            source="cfbd",
            source_team_id="2",
            name="Michigan",
            nickname="Wolverines",
            abbreviation="MICH",
            conference="Big Ten",
            division="East",
            classification="fbs"
        ),
        Team(
            league_id=cfb_league.id,
            source="cfbd",
            source_team_id="3",
            name="Ohio State",
            nickname="Buckeyes",
            abbreviation="OSU",
            conference="Big Ten",
            division="East",
            classification="fbs"
        ),
    ]
    for team in teams:
        db_session.add(team)
    db_session.commit()
    for team in teams:
        db_session.refresh(team)
    return teams


@pytest.fixture
def sample_nhl_teams(db_session, nhl_league):
    """Create sample NHL teams for multi-league testing."""
    teams = [
        Team(
            league_id=nhl_league.id,
            source="nhl",
            source_team_id="NYR",
            name="New York Rangers",
            nickname="Rangers",
            abbreviation="NYR",
            city="New York",
            state="NY",
        ),
        Team(
            league_id=nhl_league.id,
            source="nhl",
            source_team_id="BOS",
            name="Boston Bruins",
            nickname="Bruins",
            abbreviation="BOS",
            city="Boston",
            state="MA",
        ),
    ]
    for team in teams:
        db_session.add(team)
    db_session.commit()
    for team in teams:
        db_session.refresh(team)
    return teams


@pytest.fixture
def sample_venues(db_session):
    """Create sample venues for testing."""
    venues = [
        Venue(
            source="cfbd",
            source_venue_id="1",
            name="Bryant-Denny Stadium",
            city="Tuscaloosa",
            state="Alabama",
            capacity=100077
        ),
        Venue(
            source="cfbd",
            source_venue_id="2",
            name="Michigan Stadium",
            city="Ann Arbor",
            state="Michigan",
            capacity=107601
        ),
        Venue(
            source="nhl",
            source_venue_id="MSG",
            name="Madison Square Garden",
            city="New York",
            state="NY",
            capacity=18006
        ),
    ]
    for venue in venues:
        db_session.add(venue)
    db_session.commit()
    for venue in venues:
        db_session.refresh(venue)
    return venues


@pytest.fixture
def sample_games(db_session, cfb_league, sample_teams, sample_venues):
    """Create sample CFB games for testing."""
    games = [
        Game(
            league_id=cfb_league.id,
            source="cfbd",
            source_game_id="1",
            home_team_id=sample_teams[0].id,  # Alabama
            away_team_id=sample_teams[1].id,  # Michigan
            home_score=35,
            away_score=28,
            start_date=datetime(2023, 9, 2, 23, 30, 0),  # 6:30 PM Central = 11:30 PM UTC
            season=2023,
            season_type='regular',
            week=1,
            venue_id=sample_venues[0].id,
            attendance=100077
        ),
        Game(
            league_id=cfb_league.id,
            source="cfbd",
            source_game_id="2",
            home_team_id=sample_teams[1].id,  # Michigan
            away_team_id=sample_teams[2].id,  # Ohio State
            home_score=42,
            away_score=27,
            start_date=datetime(2023, 11, 25, 17, 0, 0),  # Noon Central = 5:00 PM UTC
            season=2023,
            season_type='regular',
            week=13,
            venue_id=sample_venues[1].id,
            attendance=107601
        ),
        Game(
            league_id=cfb_league.id,
            source="cfbd",
            source_game_id="3",
            home_team_id=sample_teams[0].id,  # Alabama
            away_team_id=sample_teams[2].id,  # Ohio State
            home_score=31,
            away_score=24,
            start_date=datetime(2024, 1, 2, 0, 0, 0),  # 7:00 PM Central on Jan 1 = Midnight UTC on Jan 2
            season=2023,
            season_type='postseason',
            week=None,
            venue_id=sample_venues[0].id,
            attendance=100000
        ),
    ]
    for game in games:
        db_session.add(game)
    db_session.commit()
    for game in games:
        db_session.refresh(game)
    return games


@pytest.fixture
def sample_nhl_games(db_session, nhl_league, sample_nhl_teams, sample_venues):
    """Create sample NHL games for multi-league testing."""
    games = [
        Game(
            league_id=nhl_league.id,
            source="nhl",
            source_game_id="2023020001",
            home_team_id=sample_nhl_teams[0].id,  # Rangers
            away_team_id=sample_nhl_teams[1].id,  # Bruins
            home_score=4,
            away_score=3,
            start_date=datetime(2023, 10, 12, 23, 0, 0),
            season=2023,
            season_type='regular',
            venue_id=sample_venues[2].id,  # MSG
            overtime_flag='OT',
        ),
    ]
    for game in games:
        db_session.add(game)
    db_session.commit()
    for game in games:
        db_session.refresh(game)
    return games


@pytest.fixture
def sample_attendance(db_session, test_user, sample_games):
    """Create sample attendance records for testing."""
    attendances = [
        UserGameAttendance(
            user_id=test_user.id,
            game_id=sample_games[0].id,
            notes="Great game!"
        ),
        UserGameAttendance(
            user_id=test_user.id,
            game_id=sample_games[1].id,
            notes="Amazing atmosphere"
        ),
    ]
    for attendance in attendances:
        db_session.add(attendance)
    db_session.commit()
    for attendance in attendances:
        db_session.refresh(attendance)
    return attendances
