from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: str = "sqlite:///./sports_passport.db"

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CollegeFootballData.com API (CFB league adapter)
    cfb_api_key: Optional[str] = None
    cfb_api_url: str = "https://api.collegefootballdata.com"

    # CollegeBasketballData.com API (CBB league adapter) — same maintainer/auth
    # model as CFBD, confirmed live to accept the same API key, so no separate
    # cbb_api_key setting exists; CbbAdapter reuses cfb_api_key directly.
    cbb_api_url: str = "https://api.collegebasketballdata.com"

    # League adapter data sources (free APIs used by sync_recent)
    mlb_api_url: str = "https://statsapi.mlb.com/api/v1"
    nhl_api_url: str = "https://api-web.nhle.com/v1"
    nflverse_games_url: str = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
    nba_stats_api_url: str = "https://stats.nba.com/stats"

    # Directory holding bulk historical files (Retrosheet, Kaggle CSVs, seeds)
    data_dir: str = "data"

    # Application
    app_name: str = "SportsPassport2"
    debug: bool = False

    # Nightly sync scheduler (APScheduler, in-process)
    scheduler_enabled: bool = True   # set false in tests / one-off scripts
    sync_hour: int = 6               # server-local hour (0-23) for the nightly run
    sync_lookback_days: int = 3      # window when the last run was recent / on first run

    # Sentry
    sentry_dsn: Optional[str] = None
    sentry_environment: str = "production"
    sentry_traces_sample_rate: float = 0.1

    # Password reset email (Mailtrap). Left blank in local/dev — the forgot-password
    # endpoint logs a warning and skips sending rather than failing when unset.
    mailtrap_api_key: str = ""
    app_base_url: str = "http://localhost:5173"
    from_email: str = "noreply@bronnerapp.com"
    from_name: str = "Sports Passport"
    password_reset_token_expiry_minutes: int = 15

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


settings = Settings()
