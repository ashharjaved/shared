from __future__ import annotations
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pydantic import Field


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgresql:postgres@localhost:5432/centralize_api",
    )

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production")
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")
    JWT_EXPIRE_MIN: int = int(os.getenv("JWT_EXPIRE_MIN", "60"))

    # Environment / logging
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Security knobs
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "12"))
    CONFIG_TTL_SECONDS: int = Field(default=30, description="In-process config cache TTL in seconds")

    # --- WhatsApp Messaging Gateway ---
    WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "dev-app-secret")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "dev-verify-token")
    WHATSAPP_API_BASE: str = os.getenv("WHATSAPP_API_BASE", "https://graph.facebook.com/v20.0")
    # pydantic v2 settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

@lru_cache(maxsize=1)
def _settings() -> Settings:
    return Settings()

settings = _settings()