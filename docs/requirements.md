# Requirements & Feature Status

Full product requirements for the College Football Game Tracker. Update this file when requirements change.

## Technical Decisions

- **Database**: SQLite — file-based for simplicity and portability
- **Authentication**: Email & password with JWT tokens; passwords hashed with bcrypt
- **Data Source**: [CollegeFootballData.com API](https://api.collegefootballdata.com) — free, historical data from 1990-present, manual refresh
- **User Model**: Personal/family scope. Starts with one admin user; admins can promote/demote other admins. All users track their own attendance.
- **Deployment**: Docker + Docker Compose

## Core Functionality

### 1. Game Data Management ✅
- Download and store historical D1/FBS game data from 1990-present
- Stored details: teams (home/away), final score, date, venue/stadium, week, attendance
- Manual trigger to update database with new game results
- Covers all FBS teams and games
- Both FBS and FCS teams imported to support cross-division games

### 2. User Management ✅
- Registration and authentication (email & password)
- Secure login/logout with JWT tokens
- User profile management
- Each user maintains their own attended game history
- **Admin features**: one initial admin; promote/demote admins; admin-only data refresh; list all users

### 3. Game Attendance Tracking
- Mark individual games as attended ✅
- Add notes/memories for attended games ✅
- Update or delete attendance records ✅
- Bulk attendance marking via API ✅
- Batch CSV upload for bulk import — **not yet implemented** (format TBD)

### 4. Enhanced Search & Discovery ✅
- List all teams (filter by conference or search)
- FBS teams only in dropdowns by default (overridable)
- View available seasons (with game counts)
- Filter games by team AND season
- Count games matching filters
- Get team-specific games

### 5. Statistics & Reporting ✅
**Priority:** Games by team is the most important statistic.
- Games by Team (per team) — **HIGHEST PRIORITY**
- Games by Year/Season
- Total Games Attended
- Unique Stadiums Visited
- States/Locations Visited
- View Attended Games History (filterable)

## Future Enhancements
- Mobile app support
- Social features (share attended games, find friends at games)
- Game recommendations based on attendance history
- Integration with ticketing platforms
- Photo uploads for attended games
- Stadium check-in features
- Data visualization charts
- CSV export for statistics
