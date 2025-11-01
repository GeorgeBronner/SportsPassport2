from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: str = "sqlite:///./college_football.db"

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CollegeFootballData.com API
    cfb_api_key: Optional[str] = None
    cfb_api_url: str = "https://api.collegefootballdata.com"

    # Application
    app_name: str = "College Football Game Tracker"
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
