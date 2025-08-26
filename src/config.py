# src/config.py
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Database ---
    DATABASE_URL: str = Field(..., description="PostgreSQL async URL, e.g. postgresql+asyncpg://user:pass@host/db")

    # --- JWT / Auth ---
    JWT_SECRET: str = Field(..., description="JWT HMAC/RS secret (HS256 by default)")
    JWT_ALG: str = Field("HS256", description="JWT algorithm")
    JWT_EXPIRE_MINUTES: int = Field(60, description="Access token lifetime in minutes")

    # --- Password hashing policy (read by security.get_password_hasher) ---
    PASSWORD_HASH_SCHEME: str = Field("argon2", description="argon2 | bcrypt")

    # --- App / Runtime ---
    ENV: str = Field("dev", description="Environment name")
    LOG_LEVEL: str = Field("INFO", description="Logging level")

    # --- Redis (optional) ---
    REDIS_URL: Optional[str] = Field(None, description="Redis URL, e.g. redis://localhost:6379/0")

    # --- Bootstrap (optional) ---
    # Used by initial platform-owner/tenant bootstrap logic if present.
    BOOTSTRAP_TOKEN: Optional[str] = Field(
        None,
        description="One-time bootstrap token for initial setup (optional)."
    )

        # --- Account Lockout Policy ---
    LOCKOUT_MAX_FAILED: int = Field(5, description="Max consecutive failed logins before lockout")
    LOCKOUT_COOLDOWN_MIN: int = Field(15, description="Lockout cooldown duration in minutes")

    # ----------------------------
    # Stage-2: Core Platform Config
    # ----------------------------
    # Redis-backed config cache TTL (seconds)
    CONFIG_CACHE_TTL: int = 300  # 5 minutes default
    # Rate limiting defaults (per-tenant, per-endpoint)
    RATE_LIMIT_REQUESTS: int = 1000
    RATE_LIMIT_WINDOW: int = 60  # seconds


    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Singleton accessor for Settings.
    Using lru_cache prevents repeated env parsing and avoids recursion mistakes.
    """
    # Pylance thinks BaseSettings requires args; at runtime env is used.
    return Settings()  # type: ignore[call-arg]


__all__ = ["Settings", "get_settings"]
