from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path


class StorageLimitExceeded(Exception):
    """Поток данных превысил max_bytes."""


class Storage(ABC):
    """Единственная точка доступа к файлам. Ключи относительные: 'videos/1/720.mp4'."""

    @abstractmethod
    async def save_stream(
        self, key: str, chunks: AsyncIterator[bytes], *, max_bytes: int
    ) -> int:
        """Пишет поток по ключу, возвращает размер. При любой ошибке ничего не остаётся."""

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    def local_path(self, key: str, *, for_write: bool = False) -> Path:
        """Локальный путь для ffmpeg. S3-реализация скачивала бы файл во временную папку."""

    @abstractmethod
    def internal_url(self, key: str) -> str:
        """Путь для X-Accel-Redirect. S3-реализация вернула бы presigned URL."""

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> None:
        """Удаляет всё под префиксом ('videos/5'). Если ничего нет, это не ошибка."""