"""
Centralized configuration for the WhatsApp Chatbot Platform (no external deps).

- Pure Python (dataclasses + stdlib), no Pydantic.
- Loads from OS env; optionally parses a .env file if python-dotenv is installed.
- Strong typing & validation in __post_init__.
- Immutable singleton via functools.lru_cache.
- Secrets never logged (masked).
"""

from __future__ import annotations

import functools
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlparse

# ------------------------------------------------------------------------------
# Optional .env loader (no hard dependency)
# ------------------------------------------------------------------------------
def _maybe_load_dotenv(env_path: Path) -> None:
    try:
        if env_path.exists():
            from dotenv import load_dotenv  # type: ignore
            load_dotenv(dotenv_path=str(env_path), override=False)
    except Exception:
        # dotenv not installed or failed; continue with OS env
        pass


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def _mask_secret(value: Optional[str]) -> str:
    if not value:
        return "<unset>"
    if len(value) <= 8:
        return "***"
    return value[:2] + "…" + value[-2:]


def _get_env_str(key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    v = os.getenv(key, default)
    if required and (v is None or str(v).strip() == ""):
        raise ValueError(f"Missing required env var: {key}")
    return v


def _get_env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    v = v.strip().lower()
    return v in {"1", "true", "t", "yes", "y", "on"}


def _get_env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    if v is None or v.strip() == "":
        return default
    try:
        return int(v)
    except Exception:
        raise ValueError(f"Env var {key} must be an integer")


def _validate_choice(value: str, *, choices: tuple[str, ...], key: str) -> str:
    if value not in choices:
        raise ValueError(f"{key} must be one of {choices}, got {value!r}")
    return value


def _validate_url(value: Optional[str], *, key: str, allowed_schemes: tuple[str, ...]) -> Optional[str]:
    if value in (None, ""):
        return None
    parsed = urlparse(value)
    if parsed.scheme not in allowed_schemes or not parsed.netloc:
        raise ValueError(f"{key} must be a valid URL with scheme in {allowed_schemes}")
    return value


def _validate_postgres_dsn(value: str, *, key: str) -> str:
    if not value.startswith("postgresql://") and not value.startswith("postgresql+asyncpg://"):
        raise ValueError(f"{key} must start with postgresql:// or postgresql+asyncpg://")
    return value


# ------------------------------------------------------------------------------
# Settings dataclass (immutable)
# ------------------------------------------------------------------------------
EnvName = Literal["local", "dev", "staging", "prod"]
JwtAlg = Literal["HS256", "RS256"]


@dataclass(frozen=True)
class Settings:
    # Environment
    environment: EnvName = "local"
    debug: bool = False
    is_testing: bool = False

    # Database pooling
    database_pool_size: int = 5
    database_max_overflow: int = 10


    # Core services
    database_url: str = field(default="")
    redis_url: Optional[str] = None
    secret_key: str = field(default="")
    jwt_algorithm: JwtAlg = "HS256"

    # Security / JWT
    access_token_exp_minutes: int = 15
    refresh_token_exp_minutes: int = 60 * 24 * 7  # 7 days
    auth_oidc_jwks_url: Optional[str] = None  # e.g., Auth0 JWKS (when using OIDC)
    # Optional local keys for RS256 (non-OIDC path)
    jwt_public_key: Optional[str] = None
    jwt_private_key: Optional[str] = None

    # WhatsApp / Provider
    wa_api_base_url: str = "https://graph.facebook.com/v19.0"
    wa_app_secret: Optional[str] = None  # for X-Hub-Signature verification

    # Observability
    log_level: str = "INFO"
    otel_exporter_otlp_endpoint: Optional[str] = None

    # Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)

    # Derived/computed flags (filled in __post_init__)
    is_prod: bool = field(init=False)
    is_staging: bool = field(init=False)
    is_dev: bool = field(init=False)
    is_local: bool = field(init=False)

    def __post_init__(self) -> None:
        # Validate choices
        object.__setattr__(
            self, "environment",
            _validate_choice(self.environment, choices=("local", "dev", "staging", "prod"), key="ENVIRONMENT"),
        )
        object.__setattr__(
            self, "jwt_algorithm",
            _validate_choice(self.jwt_algorithm, choices=("HS256", "RS256"), key="JWT_ALGORITHM"),
        )

        # Validate DSNs/URLs
        object.__setattr__(self, "database_url", _validate_postgres_dsn(self.database_url, key="DATABASE_URL"))
        if self.redis_url:
            _validate_url(self.redis_url, key="REDIS_URL", allowed_schemes=("redis", "rediss"))

        _validate_url(self.auth_oidc_jwks_url, key="AUTH_OIDC_JWKS_URL", allowed_schemes=("http", "https"))
        _validate_url(self.wa_api_base_url, key="WA_API_BASE_URL", allowed_schemes=("http", "https"))
        _validate_url(self.otel_exporter_otlp_endpoint, key="OTEL_EXPORTER_OTLP_ENDPOINT", allowed_schemes=("http", "https"))

        # Validate secrets
        if not self.secret_key or not self.secret_key.strip():
            raise ValueError("SECRET_KEY must be set and non-empty")

        # Validate token expiries
        if self.access_token_exp_minutes <= 0:
            raise ValueError("ACCESS_TOKEN_EXP_MINUTES must be > 0")
        if self.refresh_token_exp_minutes <= self.access_token_exp_minutes:
            raise ValueError("REFRESH_TOKEN_EXP_MINUTES must be > ACCESS_TOKEN_EXP_MINUTES")

        # Basic sanity for WA app secret (optional)
        if self.wa_app_secret is not None and len(self.wa_app_secret) < 8:
            raise ValueError("WA_APP_SECRET looks too short")

        # RS256 configuration matrix:
        # - If RS256 is selected:
        #   - Either OIDC JWKS URL must be set, OR a local public key must be provided.
        #   - If both JWKS and local keys are provided, fail fast to avoid ambiguity.
        if self.jwt_algorithm == "RS256":
            has_jwks = bool(self.auth_oidc_jwks_url)
            has_local_pub = bool(self.jwt_public_key and self.jwt_public_key.strip())
            if has_jwks and has_local_pub:
                raise ValueError("Provide either AUTH_OIDC_JWKS_URL or JWT_PUBLIC_KEY (not both) for RS256")
            if not (has_jwks or has_local_pub):
                raise ValueError("For RS256, set AUTH_OIDC_JWKS_URL or provide JWT_PUBLIC_KEY")

        # Log level basic check
        if not re.fullmatch(r"(?i)DEBUG|INFO|WARNING|ERROR|CRITICAL", self.log_level.strip()):
            raise ValueError("LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL")

        # Derived flags
        env = self.environment
        object.__setattr__(self, "is_prod", env == "prod")
        object.__setattr__(self, "is_staging", env == "staging")
        object.__setattr__(self, "is_dev", env == "dev")
        object.__setattr__(self, "is_local", env == "local")

    # Safe dict (for debug prints without secrets)
    def safe_dict(self) -> dict:
        return {
            "environment": self.environment,
            "debug": self.debug,
            "is_testing": self.is_testing,
            "database_url": "<masked>" if self.database_url else "<unset>",
            "redis_url": "<masked>" if self.redis_url else "<unset>",
            "secret_key": _mask_secret(self.secret_key),
            "jwt_algorithm": self.jwt_algorithm,
            "access_token_exp_minutes": self.access_token_exp_minutes,
            "refresh_token_exp_minutes": self.refresh_token_exp_minutes,
            "auth_oidc_jwks_url": self.auth_oidc_jwks_url or "<unset>",
            "jwt_public_key": "<masked>" if self.jwt_public_key else "<unset>",
            "jwt_private_key": "<masked>" if self.jwt_private_key else "<unset>",
            "wa_api_base_url": self.wa_api_base_url,
            "wa_app_secret": _mask_secret(self.wa_app_secret),
            "log_level": self.log_level,
            "database_pool_size": self.database_pool_size,
            "database_max_overflow": self.database_max_overflow,
            "otel_exporter_otlp_endpoint": self.otel_exporter_otlp_endpoint or "<unset>",
            "base_dir": str(self.base_dir),
        }


# ------------------------------------------------------------------------------
# Loader (singleton)
# ------------------------------------------------------------------------------
_logger = logging.getLogger(__name__)

from typing import cast

@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Attempt to load .env from repo root (../.env relative to src/)
    env_file = Path(__file__).resolve().parent.parent / ".env"
    _maybe_load_dotenv(env_file)

    settings = Settings(
        environment=cast(EnvName, _get_env_str("ENVIRONMENT", "local") or "local"),
        debug=_get_env_bool("DEBUG", False),
        is_testing=_get_env_bool("IS_TESTING", False),
        database_url=_get_env_str("DATABASE_URL", required=True) or "",
        redis_url=_get_env_str("REDIS_URL", None),
        secret_key=_get_env_str("SECRET_KEY", required=True) or "",
        jwt_algorithm=cast(JwtAlg, _get_env_str("JWT_ALGORITHM", "HS256") or "HS256"),
        access_token_exp_minutes=_get_env_int("ACCESS_TOKEN_EXP_MINUTES", 15),
        refresh_token_exp_minutes=_get_env_int("REFRESH_TOKEN_EXP_MINUTES", 60 * 24 * 7),
        auth_oidc_jwks_url=_get_env_str("AUTH_OIDC_JWKS_URL", None),
        jwt_public_key=_get_env_str("JWT_PUBLIC_KEY", None),
        jwt_private_key=_get_env_str("JWT_PRIVATE_KEY", None),
        wa_api_base_url=_get_env_str("WA_API_BASE_URL", "https://graph.facebook.com/v19.0") or "https://graph.facebook.com/v19.0",
        wa_app_secret=_get_env_str("WA_APP_SECRET", None),
        log_level=_get_env_str("LOG_LEVEL", "INFO") or "INFO",
        otel_exporter_otlp_endpoint=_get_env_str("OTEL_EXPORTER_OTLP_ENDPOINT", None),
        database_pool_size=_get_env_int("DATABASE_POOL_SIZE", 5),
        database_max_overflow=_get_env_int("DATABASE_MAX_OVERFLOW", 10),
    )

    _logger.info(
        "Settings loaded",
        extra={"settings": settings.safe_dict()}
    )
    return settings

# Convenience module-level singleton
settings = get_settings()