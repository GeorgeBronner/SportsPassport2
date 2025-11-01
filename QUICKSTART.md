# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Run Setup Script
```bash
chmod +x setup.sh
./setup.sh
```

This will:
- Create your `.env` file with a secure secret key
- Set up the data directory
- Optionally start the application

### 2. Create First Admin User

Visit the API docs at http://localhost:8000/docs

1. Register a user using `POST /api/auth/register`:
```json
{
  "email": "admin@example.com",
  "password": "your-secure-password",
  "full_name": "Your Name"
}
```

2. Make them an admin:
```bash
sqlite3 data/college_football.db "UPDATE users SET is_admin = 1 WHERE email = 'admin@example.com';"
```

### 3. Login and Get Token

Use `POST /api/auth/login` in the docs:
- username: `admin@example.com`
- password: `your-secure-password`

Click "Authorize" button in top right and paste your token.

### 4. Import Game Data

Use `POST /api/admin/refresh-data?season=2023` to import 2023 season data.

You can import multiple seasons (e.g., 2020, 2021, 2022, 2023).

### 5. Track Your First Game

1. Find a game using `GET /api/games/` or `GET /api/games/search/?q=Michigan`
2. Note the `game_id` from the results
3. Mark it as attended using `POST /api/attendance/`:
```json
{
  "game_id": 123,
  "notes": "Amazing game!"
}
```

### 6. View Your Statistics

Use `GET /api/attendance/stats` to see:
- Total games attended
- Games by team
- Games by season
- Stadiums visited
- States visited

## Common Commands

### Docker
```bash
# Start
docker compose up -d

# Stop
docker compose down

# View logs
docker compose logs -f

# Restart
docker compose restart
```

### Development
```bash
# Install dependencies
cd backend
uv pip install -e .

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Start dev server
uvicorn app.main:app --reload
```

## Enhanced Search Features

### List All Teams
```bash
# Get all teams
GET /api/teams/

# Search teams by name
GET /api/teams/?search=Alabama

# Filter by conference
GET /api/teams/?conference=SEC
```

### Get Available Seasons
```bash
GET /api/games/seasons
# Returns seasons with game counts
```

### Filter Games by Team and Season
```bash
# Get all Alabama games in 2023
GET /api/games/?team=Alabama&season=2023

# Get game count for specific filters
GET /api/games/count?team=Michigan&season=2024

# Get all games for team ID 3 (Alabama)
GET /api/games/team/3?season=2023
```

### Bulk Mark Games as Attended
```bash
POST /api/attendance/bulk
{
  "games": [
    {"game_id": 123, "notes": "Great game!"},
    {"game_id": 456, "notes": "Amazing atmosphere"},
    {"game_id": 789}
  ]
}
```

## API Quick Reference

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/auth/register` | POST | Register new user | No |
| `/api/auth/login` | POST | Login | No |
| `/api/auth/me` | GET | Get current user | Yes |
| `/api/teams/` | GET | List all teams | Yes |
| `/api/games/` | GET | List games (filter by team/season) | Yes |
| `/api/games/seasons` | GET | Get available seasons | Yes |
| `/api/games/count` | GET | Count games by filters | Yes |
| `/api/games/team/{id}` | GET | Get team's games | Yes |
| `/api/games/{id}` | GET | Get game details | Yes |
| `/api/attendance/` | POST | Mark game attended | Yes |
| `/api/attendance/bulk` | POST | Mark multiple games | Yes |
| `/api/attendance/` | GET | List attended games | Yes |
| `/api/attendance/stats` | GET | Get statistics | Yes |
| `/api/admin/refresh-data` | POST | Import data | Admin |
| `/api/admin/users` | GET | List users | Admin |

## Troubleshooting

### Can't connect to API
- Check Docker is running: `docker ps`
- Check logs: `docker compose logs -f`

### Database errors
- Restart container: `docker compose restart`
- Check migrations: `docker compose exec backend alembic current`

### Authentication errors
- Ensure you clicked "Authorize" in the API docs
- Check token hasn't expired (30 min default)

## Get CollegeFootballData.com API Key

1. Visit https://collegefootballdata.com/key
2. Sign up for a free account
3. Get your API key
4. Add to `backend/.env`: `CFB_API_KEY="your-key-here"` (use quotes if key contains special characters)
5. Restart: `docker compose restart`

The API works without a key but has rate limits. A free key gives you higher limits.
