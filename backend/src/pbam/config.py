from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str

    # Security
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # App
    environment: str = "development"
    debug: bool = False
    app_name: str = "PBAM"
    app_version: str = "0.1.0"

    # Storage
    storage_path: Path = Path("./storage")

    # CORS — use JSON array in .env: CORS_ORIGINS=["http://localhost:5173"]
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
