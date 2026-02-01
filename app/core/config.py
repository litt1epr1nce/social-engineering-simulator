"""Application configuration from environment."""
import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings loaded from env / .env."""

    app_name: str = "Social Engineering Simulator"
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./social_eng_sim.db"

    # JWT (optional for MVP)
    secret_key: str = "change-me-in-production-use-env"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Session cookie for guest
    session_cookie_name: str = "ses_session_id"
    session_cookie_max_age: int = 60 * 60 * 24 * 30  # 30 days

    # Auth cookie (session-based for logged-in users)
    auth_cookie_name: str = "ses_auth"
    auth_cookie_max_age: int = 60 * 60 * 24 * 14  # 14 days

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_settings() -> Settings:
    return Settings()


# Base path for templates/static (parent of app/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
