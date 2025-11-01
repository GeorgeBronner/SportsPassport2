# College Football Game Tracker

A web application for tracking college football games you've attended, with comprehensive statistics and historical game data from CollegeFootballData.com.

**Status:** ✅ Backend API Complete | 🚧 Frontend Coming Soon

## Features

- **User Authentication** - Email/password registration and login with JWT tokens
- **Game Database** - Historical Division 1/FBS college football games from 1990-present
- **Attendance Tracking** - Mark games as attended and add personal notes
- **Statistics Dashboard**
  - Games attended by team (highest priority)
  - Games by season/year
  - Total games attended
  - Unique stadiums visited
  - States/locations visited
- **Admin Features**
  - Data refresh from CollegeFootballData.com API
  - User management and admin promotion

## Tech Stack

### Backend
- FastAPI (Python web framework)
- SQLite (database)
- SQLAlchemy (ORM)
- Alembic (database migrations)
- JWT authentication
- CollegeFootballData.com API integration

### Deployment
- Docker & Docker Compose

## Prerequisites

- Docker and Docker Compose
- CollegeFootballData.com API key (optional, but recommended for full data access)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd SportsPassport2
```

### 2. Create Environment File

Create a `.env` file in the `backend` directory:

```bash
cd backend
cp .env.example .env
```

Edit `.env` and set your configuration:

```env
# Required - generate a secure random key
SECRET_KEY=your-super-secret-key-here

# Optional - get free API key from https://collegefootballdata.com
CFB_API_KEY=your-api-key-here
```

To generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Start with Docker Compose

From the project root:

```bash
docker compose up -d
```

This will:
- Build the backend container
- Run database migrations
- Start the API server on http://localhost:8000

### 4. Access the API

- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Development Setup (without Docker)

### 1. Install Dependencies

```bash
cd backend

# Install uv (if not already installed)
pip install uv

# Install project dependencies
uv pip install -e .
```

### 2. Set Up Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Run Database Migrations

```bash
alembic upgrade head
```

### 4. Start Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Usage

### 1. Register a User

```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword",
    "full_name": "John Doe"
  }'
```

### 2. Login

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=securepassword"
```

This returns an access token. Use it in subsequent requests:

```bash
TOKEN="your-access-token-here"
```

### 3. Import Game Data (Admin Only)

First, manually set a user as admin in the database, then:

```bash
curl -X POST "http://localhost:8000/api/admin/refresh-data?season=2023" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Mark Game as Attended

```bash
curl -X POST "http://localhost:8000/api/attendance/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": 1,
    "notes": "Amazing game! Great atmosphere."
  }'
```

### 5. Get Your Statistics

```bash
curl -X GET "http://localhost:8000/api/attendance/stats" \
  -H "Authorization: Bearer $TOKEN"
```

## Database Schema

- **users** - User accounts and authentication
- **teams** - College football teams
- **venues** - Stadiums and game locations
- **games** - Individual game records
- **user_game_attendance** - Tracks user attendance with notes

## Creating Database Migrations

When you modify models:

```bash
cd backend
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

## Setting First Admin User

After registering your first user, make them an admin:

### Option 1: Using SQLite CLI (from host machine)

```bash
sqlite3 data/college_football.db "UPDATE users SET is_admin = 1 WHERE email = 'your@email.com';"
```

### Option 2: Using Docker exec with Python

```bash
docker exec cfb-tracker-backend python -c "
from college_football_tracker.db.database import SessionLocal
from college_football_tracker.models.user import User

db = SessionLocal()
user = db.query(User).filter(User.email == 'your@email.com').first()
if user:
    user.is_admin = True
    db.commit()
    print(f'User {user.email} is now an admin')
db.close()
"
```

## Project Structure

```
SportsPassport2/
├── backend/
│   ├── app/
│   │   ├── core/           # Config, security, dependencies
│   │   ├── db/             # Database setup
│   │   ├── models/         # SQLAlchemy models
│   │   ├── routers/        # API endpoints
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic (CFB API client)
│   │   └── main.py         # FastAPI application
│   ├── alembic/            # Database migrations
│   ├── pyproject.toml      # Python dependencies
│   ├── Dockerfile
│   └── .env
├── docker-compose.yml
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get token
- `GET /api/auth/me` - Get current user info

### Games
- `GET /api/games/` - List games (with filters)
- `GET /api/games/{id}` - Get game details
- `GET /api/games/search/` - Search games by team

### Attendance
- `POST /api/attendance/` - Mark game as attended
- `GET /api/attendance/` - List attended games
- `GET /api/attendance/stats` - Get attendance statistics
- `PATCH /api/attendance/{id}` - Update attendance notes
- `DELETE /api/attendance/{id}` - Remove attendance record

### Admin
- `POST /api/admin/refresh-data` - Import data from API
- `GET /api/admin/users` - List all users
- `POST /api/admin/users/{id}/promote` - Promote user to admin
- `POST /api/admin/users/{id}/demote` - Demote user from admin

## Future Enhancements

- [ ] CSV bulk upload for attendance
- [ ] React frontend
- [ ] Mobile app
- [ ] Photo uploads for games
- [ ] Social features
- [ ] Game recommendations

## Get CollegeFootballData.com API Key

1. Visit https://collegefootballdata.com/key
2. Sign up for a free account
3. Get your API key
4. Add to `backend/.env`: `CFB_API_KEY="your-key-here"` (use quotes if key contains special characters)
5. Restart: `docker compose restart`

Note: The API works without a key but has rate limits. A free key provides higher limits.
