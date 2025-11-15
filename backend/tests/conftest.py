"""
Pytest configuration and fixtures for testing.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, date

from college_football_tracker.main import app
from college_football_tracker.db.database import Base, get_db
from college_football_tracker.models.user import User
from college_football_tracker.models.team import Team
from college_football_tracker.models.venue import Venue
from college_football_tracker.models.game import Game
from college_football_tracker.models.attendance import UserGameAttendance
from college_football_tracker.core.security import get_password_hash


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
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with dependency injection."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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
def sample_teams(db_session):
    """Create sample teams for testing."""
    teams = [
        Team(
            api_team_id=1,
            school="Alabama",
            mascot="Crimson Tide",
            abbreviation="ALA",
            conference="SEC",
            division="West",
            classification="fbs"
        ),
        Team(
            api_team_id=2,
            school="Michigan",
            mascot="Wolverines",
            abbreviation="MICH",
            conference="Big Ten",
            division="East",
            classification="fbs"
        ),
        Team(
            api_team_id=3,
            school="Ohio State",
            mascot="Buckeyes",
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
def sample_venues(db_session):
    """Create sample venues for testing."""
    venues = [
        Venue(
            api_venue_id=1,
            name="Bryant-Denny Stadium",
            city="Tuscaloosa",
            state="Alabama",
            capacity=100077
        ),
        Venue(
            api_venue_id=2,
            name="Michigan Stadium",
            city="Ann Arbor",
            state="Michigan",
            capacity=107601
        ),
    ]
    for venue in venues:
        db_session.add(venue)
    db_session.commit()
    for venue in venues:
        db_session.refresh(venue)
    return venues


@pytest.fixture
def sample_games(db_session, sample_teams, sample_venues):
    """Create sample games for testing."""
    games = [
        Game(
            api_game_id=1,
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
            api_game_id=2,
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
            api_game_id=3,
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
