# Testing

- **Framework**: pytest with dependency injection
- **Test Database**: in-memory SQLite for isolation (no impact on production data)
- **Coverage**: 94 tests covering all endpoints

## Test Structure
| File | Scope | Tests |
|------|-------|-------|
| `backend/tests/conftest.py` | Fixtures and test database setup | — |
| `backend/tests/test_auth.py` | Authentication | 12 |
| `backend/tests/test_teams.py` | Team listing | 7 |
| `backend/tests/test_games.py` | Game endpoints | 26 |
| `backend/tests/test_attendance.py` | Attendance tracking | 29 |
| `backend/tests/test_admin.py` | Admin endpoints | 20 |

## Running Tests
```bash
# All tests
docker compose exec backend pytest tests/ -v

# Specific file
docker compose exec backend pytest tests/test_auth.py -v

# Specific test
docker compose exec backend pytest tests/test_auth.py::TestUserLogin::test_login_success -v

# With coverage
docker compose exec backend pytest tests/ --cov=college_football_tracker --cov-report=term-missing
```

## Test Features
- Isolated test database
- Dependency injection for FastAPI endpoints
- Comprehensive fixtures for users, teams, games, venues, attendance
- JWT authentication and admin permission testing
- Mock testing for external API calls
