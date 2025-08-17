from __future__ import annotations
import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/whatsapp",
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

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
