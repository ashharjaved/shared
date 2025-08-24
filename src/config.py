from functools import lru_cache
from pydantic_settings import BaseSettings  # if using Pydantic v2
# or: from pydantic import BaseSettings  # if still on v1

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    BOOTSTRAP_TOKEN: str
    REDIS_URL:str

    JWT_ALG: str = "HS256"
    JWT_EXPIRES_MIN: int = 60
    PASSWORD_HASH_SCHEME: str = "argon2"
    LOCKOUT_MAX_FAILED: int = 5
    LOCKOUT_COOLDOWN_MIN: int = 15

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache
def get_settings() -> Settings:
    return get_settings()   # no arguments, values pulled from env/.env
