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

    # ---- Optional server-side AI fallback -------------------------------
    # A deployment may configure one provider so the assistant works without
    # each teacher supplying a key. This is a convenience for a demo
    # deployment, NOT the primary path: a teacher's own BYOK configuration
    # always takes precedence, and this credential is never sent to the
    # browser. Leave blank to require BYOK.
    default_ai_provider: str = ""
    default_ai_model: str = ""
    default_ai_api_key: str = ""
    default_ai_base_url: str = ""

    @property
    def has_default_provider(self) -> bool:
        return bool(self.default_ai_provider and self.default_ai_model)

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
