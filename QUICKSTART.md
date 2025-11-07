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

### 2. Access the Application

Visit http://localhost:8000 to access the web interface.

### 3. Create First Admin User

1. Click "Sign up" and create your account
2. Make yourself an admin:
```bash
sqlite3 data/college_football.db "UPDATE users SET is_admin = 1 WHERE email = 'your@email.com';"
```

### 4. Import Game Data

As an admin:
1. Go to the Admin page
2. Enter a season year (e.g., 2023, 2024, 2025)
3. Click "Import Season Data"
4. Repeat for multiple seasons if desired

### 5. Track Your First Game

1. Go to the "Games" page
2. Use filters to find games (by team or season)
3. Click "Mark Attended" on any game
4. Optionally add notes about the game

### 6. View Your Statistics

Visit the "Statistics" page to see:
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

Use this command to push and deploy to oracle.
git push origin main && ssh oracle "cd SportsPassport2 && git pull origin main && docker compose up -d --build"
