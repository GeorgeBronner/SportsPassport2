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

## Future Enhancements
- Mobile app support
- Social features (share attended games, find friends at games)
- Game recommendations based on attendance history
- Integration with ticketing platforms
- Photo uploads for attended games
- Stadium check-in features
