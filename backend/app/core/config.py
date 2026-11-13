from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфиг только из переменных окружения (в Docker их подаёт compose из .env)."""

    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "dev"
    database_url: str  # обязательная: без неё приложение не стартует
    secret_key: str = "dev-insecure-change-me"
    cookie_secure: bool = False
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    @model_validator(mode="after")
    def _check_prod_secret(self) -> "Settings":
        weak = len(self.secret_key) < 32 or self.secret_key.startswith(("dev-", "change-me"))
        if self.app_env == "prod" and weak:
            raise ValueError("SECRET_KEY must be a strong random value when APP_ENV=prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()