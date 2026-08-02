
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: str = "sqlite:///./sports_passport.db"

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CollegeFootballData.com API (CFB league adapter)
    cfb_api_key: str | None = None
    cfb_api_url: str = "https://api.collegefootballdata.com"

    # CollegeBasketballData.com API (CBB league adapter) — same maintainer/auth
    # model as CFBD, confirmed live to accept the same API key, so no separate
    # cbb_api_key setting exists; CbbAdapter reuses cfb_api_key directly.
    cbb_api_url: str = "https://api.collegebasketballdata.com"

    # League adapter data sources (free APIs used by sync_recent)
    mlb_api_url: str = "https://statsapi.mlb.com/api/v1"
    nhl_api_url: str = "https://api-web.nhle.com/v1"
    nflverse_games_url: str = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
    # NBA sync runs on ESPN, not stats.nba.com: every nba.com host (stats. and
    # cdn.) answers Akamai "Access Denied" from both the Oracle production host
    # and a residential connection, with or without browser-shaped headers, so
    # the originally-planned scoreboardv2 sync could never run anywhere.
    # SP3_data_sources.md already lists ESPN as NBA's backup update source.
    espn_api_url: str = "https://site.api.espn.com/apis/site/v2/sports"

    # Directory holding bulk historical files (Retrosheet, Kaggle CSVs)
    data_dir: str = "data"

    # Application
    app_name: str = "SportsPassport2"
    debug: bool = False

    # CORS. The SPA is served by this same app, so no cross-origin access is
    # needed in production; the default covers the Vite dev server only. Set
    # CORS_ORIGINS to a comma-separated list to allow other origins.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Rate limiting (login, forgot/reset-password). Disabled in tests so the
    # suite's repeated logins don't trip the limiter.
    rate_limit_enabled: bool = True

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_origin(cls, v: str) -> str:
        """Fail startup on CORS_ORIGINS=*, rather than honouring it.

        The middleware runs with allow_credentials, and Starlette answers a
        wildcard by echoing back whatever Origin asked — so "*" would hand any
        site credentialed access to this API. Refusing it at config load makes
        that a startup failure an operator sees immediately, instead of a
        silently permissive deployment.
        """
        if any(o.strip() == "*" for o in v.split(",")):
            raise ValueError(
                "CORS_ORIGINS must list explicit origins; '*' is unsafe with "
                "credentialed requests"
            )
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Nightly sync scheduler (APScheduler, in-process)
    scheduler_enabled: bool = True   # set false in tests / one-off scripts
    sync_hour: int = 6               # server-local hour (0-23) for the nightly run
    sync_lookback_days: int = 3      # window when the last run was recent / on first run

    # Sentry
    sentry_dsn: str | None = None
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


# secret_key is deliberately given no default so a missing SECRET_KEY fails at
# import rather than silently signing tokens with a guessable value.
# pydantic-settings supplies it from the environment / .env, which a type
# checker can't see — hence the ignore on the otherwise-argumentless call.
settings = Settings()  # pyright: ignore[reportCallIssue]
