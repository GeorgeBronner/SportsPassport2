# College Football Game Tracker - Requirements

**IMPORTANT: Always update this file when any requirements change.**

## Overview
An application that allows users to track college football games they have attended, with comprehensive statistics and historical game data. This is designed for personal/family use with Docker deployment.

## Technical Decisions

### Database
- **SQLite** - File-based database for simplicity and portability

### Authentication
- **Email & Password** - Traditional authentication with JWT tokens
- Password hashing using bcrypt

### Data Source
- **CollegeFootballData.com API** - Free, comprehensive college football data API
- Historical data from 1990-present
- Manual refresh capability for new games

### User Model
- Personal/Family use scope
- Start with one admin user
- Admins can promote other users to admin status
- All users can track their own game attendance

### Deployment
- **Docker** containerized deployment
- Docker Compose for orchestration

## Core Functionality

### 1. Game Data Management ✅
- Download and store historical Division 1/FBS college football game data from 1990-present ✅
- Store the following game details:
  - **Teams** (home team and away team) ✅
  - **Score** (final score for both teams) ✅
  - **Date** (game date) ✅
  - **Location/Stadium** (venue information) ✅
  - **Week** (game week) ✅
  - **Attendance** (stadium attendance) ✅
- Provide manual trigger to update database with new game results ✅
- Data should cover all FBS teams and games ✅
- Source: CollegeFootballData.com API ✅

### 2. User Management ✅
- User registration and authentication system (Email & Password) ✅
- Secure login/logout functionality with JWT tokens ✅
- User profile management ✅
- Each user maintains their own attended game history ✅
- **Admin Features:** ✅
  - Start with one admin user ✅
  - Admins can promote other users to admin status ✅
  - Admins can demote users from admin status ✅
  - Admin-only access to data refresh endpoints ✅
  - Admin can list all users ✅

### 3. Game Attendance Tracking
- Users can mark individual games as attended ✅
- Users can add notes/memories for attended games ✅
- Users can update or delete attendance records ✅
- **Bulk attendance marking via API** (mark multiple games at once) ✅
- **Batch CSV upload for bulk game attendance import** (To be implemented in later phase - format TBD)

### 4. Enhanced Search & Discovery ✅
- **List all teams** (with filtering by conference or search) ✅
- **View available seasons** (with game counts per season) ✅
- **Filter games by team AND season** (combined filtering) ✅
- **Count games** matching specific filters ✅
- **Get team-specific games** (all games for a specific team) ✅

### 5. Statistics & Reporting
**Priority:** Games by team is the most important statistic

All statistics implemented:
- **Games by Team** (games attended per team) - **HIGHEST PRIORITY** ✅
- **Games by Year/Season** (breakdown by year) ✅
- **Total Games Attended** (overall count) ✅
- **Unique Stadiums Visited** (distinct venues) ✅
- **States/Locations Visited** (geographic tracking) ✅
- **View Attended Games History** (filterable list) ✅

## Technical Stack

### Backend
- **FastAPI** (Python web framework)
- **SQLite** (database)
- **SQLAlchemy** (ORM)
- **Alembic** (database migrations)
- **JWT** (authentication tokens)
- **Bcrypt** (password hashing)
- **Pydantic** (data validation)
- **CollegeFootballData.com API** (data source)

### Frontend (Future Phase)
- React
- REST API consumption

### Deployment ✅
- **Docker** (containerization) ✅
- **Docker Compose** (orchestration) ✅
- **Automated setup script** ✅
- **Health check endpoints** ✅
- **Alembic migrations auto-run on startup** ✅

## Development Best Practices

### Git Workflow
- Use feature branches for all new features/changes
- Branch naming: `feature-name` (e.g., `enhanced-search`)
- Merge to `main` when feature is complete and tested
- **Commit Messages:**
  - Keep messages concise and focused
  - NEVER mention Claude, AI, or code generation tools in commit messages
  - Focus on what changed and why, not how it was created
- **ALWAYS rebuild and restart Docker after merging to main:**
  ```bash
  docker compose up -d --build
  ```
- Verify app starts successfully after rebuild:
  ```bash
  docker logs cfb-tracker-backend --tail 10
  ```

### Code Organization
- Keep routers focused and organized by domain (auth, games, teams, attendance, admin)
- Add new schemas to appropriate schema files
- Update documentation (README.md, QUICKSTART.md, CLAUDE.md) with new features
- Test new endpoints before committing

### Testing ✅
- **Framework**: pytest with dependency injection
- **Test Database**: In-memory SQLite for isolation
- **Coverage**: 94 tests covering all endpoints
- **Test Structure**:
  - `backend/tests/conftest.py` - Fixtures and test database setup
  - `backend/tests/test_auth.py` - Authentication tests (12 tests)
  - `backend/tests/test_teams.py` - Team listing tests (7 tests)
  - `backend/tests/test_games.py` - Game endpoints tests (26 tests)
  - `backend/tests/test_attendance.py` - Attendance tracking tests (29 tests)
  - `backend/tests/test_admin.py` - Admin endpoint tests (20 tests)

**Running Tests:**
```bash
# Run all tests
docker compose exec backend pytest tests/ -v

# Run specific test file
docker compose exec backend pytest tests/test_auth.py -v

# Run specific test
docker compose exec backend pytest tests/test_auth.py::TestUserLogin::test_login_success -v

# Run with coverage
docker compose exec backend pytest tests/ --cov=college_football_tracker --cov-report=term-missing
```

**Test Features:**
- Isolated test database (no impact on production data)
- Dependency injection for FastAPI endpoints
- Comprehensive fixtures for users, teams, games, venues, attendance
- Authentication testing with JWT tokens
- Admin permission testing
- Mock testing for external API calls

## Future Enhancements
- Mobile app support
- Social features (share attended games, find friends at games)
- Game recommendations based on attendance history
- Integration with ticketing platforms
- Photo uploads for attended games
- Stadium check-in features
