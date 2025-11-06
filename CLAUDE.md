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
- **FBS vs FCS games**: Both FBS and FCS teams are imported to support games between divisions ✅
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
- **FBS teams only in dropdowns** (defaults to showing only FBS teams, can be overridden) ✅
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

### Frontend ✅
- **React 18** with TypeScript ✅
- **Vite** (build tool) ✅
- **Tailwind CSS** (styling) ✅
- **React Router v6** (navigation) ✅
- **Axios** (HTTP client with JWT interceptors) ✅
- REST API consumption ✅

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

## Frontend Implementation ✅

### Pages
- **Login/Register** - Authentication pages with form validation ✅
- **Dashboard** - Overview with key stats and top teams ✅
- **Games** - Browse and search games with filters (team, season) ✅
- **My Games** - View attended games with notes management ✅
- **Statistics** - Detailed stats breakdown (teams, seasons, stadiums, states) ✅
- **Admin** - Data refresh and user management (admin only) ✅

### Key Features
- **Protected Routes** - Authentication required for all pages except login/register ✅
- **Admin Routes** - Admin-only pages with permission checking ✅
- **Responsive Design** - Mobile-friendly with Tailwind CSS ✅
- **Real-time Updates** - Inline attendance marking without page reload ✅
- **Error Handling** - User-friendly error messages and loading states ✅
- **JWT Token Management** - Auto-attach to requests, auto-redirect on expiry ✅

### Build & Deployment
- **Static Build** - Vite builds to `backend/static/` ✅
- **FastAPI Serving** - Backend serves frontend via StaticFiles ✅
- **Docker Multi-stage Build** - Frontend built in Node container, copied to Python container ✅
- **Single Port Deployment** - Everything served on port 8000 ✅

### Development Workflow
```bash
# Frontend development mode (with hot reload)
cd frontend && npm run dev  # http://localhost:5173

# Build frontend for production
cd frontend && npm run build  # Outputs to backend/static/

# Full Docker build (includes frontend)
docker compose up -d --build
```

## Production Deployment

### Oracle Server Configuration
- **Server**: Oracle Cloud Ubuntu instance
- **Access**: SSH via `oracle` alias
- **Docker Context**: `oracle`
- **Project Path**: `/home/ubuntu/SportsPassport2`
- **Port**: 8001 (mapped to container's 8000)
- **Network**: `nginx-proxy` (shared with nginx-proxy-manager)

### Environment Setup
The production server requires a `.env` file at `backend/.env` with the following variables:
```bash
# Database
DATABASE_URL=sqlite:////app/data/college_football.db

# Security (generate unique SECRET_KEY for production)
SECRET_KEY=<generated-secret-key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CollegeFootballData.com API
CFB_API_KEY=<api-key>
CFB_API_URL=https://api.collegefootballdata.com

# Application
APP_NAME=College Football Game Tracker
DEBUG=False
```

**Generate SECRET_KEY:**
```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

### Deployment Workflow

**Prerequisites:**
- All changes committed and pushed to GitHub `main` branch
- Docker context `oracle` configured and accessible

**Standard Deployment Process:**

1. **Commit and Push Changes Locally**
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```

2. **Pull Changes on Oracle Server**
   ```bash
   ssh oracle "cd SportsPassport2 && git pull origin main"
   ```

3. **Rebuild and Restart Containers**
   ```bash
   ssh oracle "cd SportsPassport2 && docker compose up -d --build"
   ```

4. **Verify Deployment**
   ```bash
   # Check container status
   docker --context oracle ps | grep cfb-tracker

   # Check logs for successful startup
   docker --context oracle logs cfb-tracker-backend --tail 20

   # Verify health
   docker --context oracle exec cfb-tracker-backend curl -f http://localhost:8000/health
   ```

**One-Line Deployment (if no .env changes needed):**
```bash
git push origin main && ssh oracle "cd SportsPassport2 && git pull origin main && docker compose up -d --build"
```

### Network Configuration

The application must be on the `nginx-proxy` network to be accessible through nginx-proxy-manager:

```yaml
# docker-compose.yml
services:
  backend:
    networks:
      - nginx-proxy
    # ... other config

networks:
  nginx-proxy:
    external: true
```

**Verify Network Configuration:**
```bash
# Check which network the container is on
docker --context oracle inspect cfb-tracker-backend --format '{{range $net, $config := .NetworkSettings.Networks}}{{$net}}{{end}}'

# List all containers on nginx-proxy network
docker --context oracle network inspect nginx-proxy --format '{{range .Containers}}{{.Name}}: {{.IPv4Address}} {{end}}'
```

### Common Production Commands

```bash
# View logs
docker --context oracle logs cfb-tracker-backend --tail 50 -f

# Restart without rebuild
ssh oracle "cd SportsPassport2 && docker compose restart"

# Stop containers
ssh oracle "cd SportsPassport2 && docker compose down"

# Execute command in container
docker --context oracle exec cfb-tracker-backend <command>

# Access container shell
docker --context oracle exec -it cfb-tracker-backend sh

# Check container health
docker --context oracle inspect cfb-tracker-backend --format '{{.State.Health.Status}}'

# View running containers
docker --context oracle ps
```

### Troubleshooting

**Container won't start:**
1. Check logs: `docker --context oracle logs cfb-tracker-backend`
2. Common issues:
   - Missing or invalid `.env` file
   - Database connection problems
   - Port conflicts

**Network connectivity issues:**
1. Verify container is on nginx-proxy network
2. Check nginx-proxy-manager configuration
3. Test internal connectivity: `docker --context oracle exec cfb-tracker-backend curl http://localhost:8000/health`

**After deployment changes:**
- Frontend changes require rebuild (included in `--build`)
- Python dependency changes require rebuild
- Configuration changes may only need restart
- Database schema changes run automatically via Alembic migrations

## Future Enhancements
- Mobile app support
- Social features (share attended games, find friends at games)
- Game recommendations based on attendance history
- Integration with ticketing platforms
- Photo uploads for attended games
- Stadium check-in features
- Data visualization charts
- CSV export for statistics
