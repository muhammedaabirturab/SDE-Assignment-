"""Application configuration, read from environment variables / a .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. No credentials are hardcoded: ``DATABASE_URL`` is required."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    app_name: str = "Expense Sharing Service"
    app_version: str = "1.0.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
