from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфиг только из переменных окружения (в Docker их подаёт compose из .env)."""

    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "dev"
    database_url: str  # обязательная: без неё приложение не стартует
    secret_key: str = "SFLMbdvaHNIviaYhHJVhxOWfB7iCtD7I6scIJy-4vo4E9DSJ7gukrqSw0dvxw184"
    cookie_secure: bool = False
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    media_root: str = "/data/media"
    max_upload_mb: int = 500  # держи в синхроне с client_max_body_size в nginx/nginx.conf
    job_max_attempts: int = 3
    job_stale_seconds: int = 2400
    ffmpeg_step_timeout_seconds: int = 1800
    worker_poll_seconds: float = 2.0
    pending_ttl_hours: int = 24  # видео без загруженного файла удаляются через столько часов
    allowed_origins: str = ""  # доп. источники для проверки Origin, через запятую

    @model_validator(mode="after")
    def _check_prod_secret(self) -> "Settings":
        weak = len(self.secret_key) < 32 or self.secret_key.startswith(("dev-", "change-me"))
        if self.app_env == "prod" and weak:
            raise ValueError("SECRET_KEY must be a strong random value when APP_ENV=prod")
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def allowed_origins_set(self) -> set[str]:
        return {o.strip().rstrip("/").lower() for o in self.allowed_origins.split(",") if o.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()