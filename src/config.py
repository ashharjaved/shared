# src/config.py

from functools import lru_cache
from typing import Optional, List, Union

from pydantic import Field, AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Central application settings (Pydantic v2).

    - Aliases match your .env keys:
      APP_NAME, ENV, JWT_ALG, JWT_EXPIRES_MIN,
      CONFIG_TTL_SECONDS, BOOTSTRAP_TOKEN, PASSWORD_HASH_SCHEME,
      LOCKOUT_MAX_FAILED, LOCKOUT_COOLDOWN_MIN
    - No duplicate field declarations.
    """

    # ------------------------------------------------------------------------------------
    # App / API
    # ------------------------------------------------------------------------------------
    PROJECT_NAME: str = Field(default="whatsapp-chatbot-platform", alias="APP_NAME")
    ENVIRONMENT: str = Field(default="dev", alias="ENV")  # dev|staging|prod
    API_V1_STR: str = Field(default="/api")
    PROJECT_VERSION: str = Field(default="1.0.0")
    LOG_LEVEL: str = Field(default="INFO")

    # ------------------------------------------------------------------------------------
    # Database / Redis
    # ------------------------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:123456@localhost:5432/centralize_api",
        description="Async SQLAlchemy URL (postgresql+asyncpg)",
    )
    TEST_DATABASE_URL: Optional[str] = Field(default=None)
    REDIS_URL: Optional[str] = Field(default="redis://localhost:6379/0")

    # ------------------------------------------------------------------------------------
    # JWT / Auth
    # ------------------------------------------------------------------------------------
    JWT_SECRET: str = Field(
        default="super-long-very-random-secret-change-me-now",
        description="HS256 secret or RS256 private key (never commit real secrets)",
    )
    JWT_ALGORITHM: str = Field(default="HS256", alias="JWT_ALG")  # HS256 | RS256
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, alias="JWT_EXPIRES_MIN")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # Optional RS256 keys
    JWT_PRIVATE_KEY: Optional[str] = Field(default=None, description="PEM private key")
    JWT_PUBLIC_KEY: Optional[str] = Field(default=None, description="PEM public key")

    # ------------------------------------------------------------------------------------
    # Security / Passwords / Lockout
    # ------------------------------------------------------------------------------------
    PASSWORD_HASH_SCHEME: str = Field(default="argon2")  # or bcrypt
    PASSWORD_MIN_LENGTH: int = Field(default=8)
    MAX_LOGIN_ATTEMPTS: int = Field(default=5, alias="LOCKOUT_MAX_FAILED")
    ACCOUNT_LOCKOUT_MINUTES: int = Field(default=15, alias="LOCKOUT_COOLDOWN_MIN")
    BOOTSTRAP_TOKEN: str = Field(default="change-me-bootstrap")
    REFRESH_TOKEN_EXPIRE_MINUTES:int = Field(default=15)

    # ------------------------------------------------------------------------------------
    # CORS / Web
    # ------------------------------------------------------------------------------------
    BACKEND_CORS_ORIGINS: Union[List[str], str] = Field(
    default_factory=lambda: [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]
    )
    BASE_URL: Optional[AnyHttpUrl] = Field(default=None)

    # ------------------------------------------------------------------------------------
    # Platform / Cache TTLs
    # ------------------------------------------------------------------------------------
    CONFIG_TTL_SECONDS: int = Field(default=60)

    # ------------------------------------------------------------------------------------
    # Feature Flags / Misc
    # ------------------------------------------------------------------------------------
    TESTING: bool = Field(default=False)
    ENABLE_RATE_LIMITING: bool = Field(default=True)
    ENABLE_OUTBOX_WORKER: bool = Field(default=True)

    # ------------------------------------------------------------------------------------
    # Helper properties
    # ------------------------------------------------------------------------------------
    @property
    def is_dev(self) -> bool:
        return self.ENVIRONMENT.lower() in {"dev", "development", "local"}

    @property
    def is_staging(self) -> bool:
        return self.ENVIRONMENT.lower() in {"stage", "staging"}

    @property
    def is_prod(self) -> bool:
        return self.ENVIRONMENT.lower() in {"prod", "production"}

    @property
    def jwt_is_rs256(self) -> bool:
        return self.JWT_ALGORITHM.upper() == "RS256"

    def cors_origins(self) -> List[str]:
        if isinstance(self.BACKEND_CORS_ORIGINS, list):
            return self.BACKEND_CORS_ORIGINS
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]
        return []

    @property
    def effective_database_url(self) -> str:
        if self.TESTING and self.TEST_DATABASE_URL:
            return self.TEST_DATABASE_URL
        return self.DATABASE_URL

    def get_jwt_secret(self) -> str:
        if self.jwt_is_rs256 and self.JWT_PRIVATE_KEY:
            return self.JWT_PRIVATE_KEY
        return self.JWT_SECRET

    def get_jwt_public_key(self) -> Optional[str]:
        if self.jwt_is_rs256:
            return self.JWT_PUBLIC_KEY
        return None

    # ------------------------------------------------------------------------------------
    # Pydantic v2 settings config
    # ------------------------------------------------------------------------------------
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "populate_by_name": True,   # enable aliases
        "extra": "ignore",          # don't crash on unrelated env keys
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Convenient singleton: from src.config import settings
settings = get_settings()
