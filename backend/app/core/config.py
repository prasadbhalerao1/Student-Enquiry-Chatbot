"""Application settings, loaded from environment / backend/.env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://localhost/csbs"
    session_secret: str = "dev-only-insecure-secret-change-me"
    frontend_origin: str = "http://localhost:3000"

    # Illustrative demo threshold. NOT a verified college regulation.
    attendance_threshold: float = 75.0

    cookie_secure: bool = False
    session_max_age: int = 60 * 60 * 8  # 8 hours

    # Guard rails for chat requests.
    max_chat_chars: int = 8000
    max_chat_messages: int = 40
    upstream_timeout: int = 120

    @property
    def sqlalchemy_url(self) -> str:
        """Normalise a bare postgresql:// URL onto the psycopg v3 driver."""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
