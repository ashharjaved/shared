# from __future__ import annotations
# import os
# from pydantic_settings import BaseSettings, SettingsConfigDict
# from functools import lru_cache
# from pydantic import Field, SecretStr


# class Settings(BaseSettings):
#     DATABASE_URL: str = os.getenv(
#         "DATABASE_URL",
#         "postgresql+asyncpg://postgresql:postgres@localhost:5432/centralize_api",
#     )
#     DB_ECHO: bool = Field(default=False, description="Enable SQLAlchemy engine echo (debug only)")

#     # JWT
#     JWT_SECRET: SecretStr = Field(..., description="HMAC secret for JWT")
#     JWT_ALG: str = os.getenv("JWT_ALG", "HS256")
#     JWT_EXPIRE_MIN: int = int(os.getenv("JWT_EXPIRE_MIN", "60"))

#     # Environment / logging
#     ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
#     DEBUG: bool = ENVIRONMENT == "development"
#     LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

#     # Security knobs
#     BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "12"))
#     CONFIG_TTL_SECONDS: int = Field(default=30, description="In-process config cache TTL in seconds")

#     # --- WhatsApp Messaging Gateway ---
#     WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "dev-app-secret")
#     WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "dev-verify-token")
#     WHATSAPP_API_BASE: str = os.getenv("WHATSAPP_API_BASE", "https://graph.facebook.com/v21.0")
#     # pydantic v2 settings config
#     model_config = SettingsConfigDict(
#         env_file=".env",
#         env_file_encoding="utf-8",
#         case_sensitive=True,
#     )

# @lru_cache(maxsize=1)
# def _settings() -> Settings:
#     return Settings()

# settings = _settings()
#########-------------------------------------------------------------
from __future__ import annotations
from functools import lru_cache

"""
Centralized application settings (Pydantic v2).

Reads from environment variables and optional `.env` at the repo root.

Required (no safe defaults in prod):
  - DATABASE_URL
  - JWT_SECRET
  - WHATSAPP_APP_SECRET
  - WHATSAPP_VERIFY_TOKEN

Common:
  - JWT_ALG (default "HS256")
  - JWT_EXPIRE_MIN (default 60)
  - CONFIG_TTL_SECONDS (default 60)
  - DB_ECHO (default False)
  - DB_STATEMENT_TIMEOUT_MS (optional int, milliseconds)
"""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read .env (if present) and environment variables (case-insensitive keys)
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # --- Runtime / environment ---
    ENV: str = Field(default="dev", description="Environment name: dev|staging|prod")

    # --- Database ---
    DATABASE_URL: str = Field(description="Async SQLAlchemy URL, e.g. postgresql+asyncpg://postgres:123456@host:5432/centralize_api")
    DB_ECHO: bool = Field(default=False, description="Echo SQLAlchemy statements (debug only)")
    DB_STATEMENT_TIMEOUT_MS: int | None = Field(
        default=None, description="Optional per-connection statement_timeout (ms)"
    )

    # --- Auth / JWT ---
    JWT_SECRET: SecretStr = Field(description="HMAC secret for JWT signing/verification")
    JWT_ALG: str = Field(default="HS256", description="JWT algorithm")
    JWT_EXPIRE_MIN: int = Field(default=60, description="JWT expiration in minutes")

    # --- Platform Config Cache ---
    CONFIG_TTL_SECONDS: int = Field(default=60, description="TTL for in-process config cache")

    # --- WhatsApp Cloud API ---
    WHATSAPP_APP_SECRET: SecretStr | str = Field(description="App secret used for webhook signature validation")
    WHATSAPP_VERIFY_TOKEN: str = Field(description="Verification token used in webhook GET challenge")
    WHATSAPP_API_BASE: str | None = Field(
        default=None, description="Optional Graph base URL override (e.g., https://graph.facebook.com/v20.0)"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton Settings instance (cached)."""
    return Settings()

# Export a conventional module-level instance for `from src.config import settings`
settings = get_settings()