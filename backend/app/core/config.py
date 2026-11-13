from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфиг только из переменных окружения (в Docker их подаёт compose из .env)."""

    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "dev"
    database_url: str  # обязательная: без неё приложение не стартует
    secret_key: str = "dev-insecure-change-me"
    cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()