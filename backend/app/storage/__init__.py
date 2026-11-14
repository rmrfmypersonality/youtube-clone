from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.storage.base import Storage, StorageLimitExceeded
from app.storage.disk import DiskStorage


@lru_cache
def get_storage() -> Storage:
    return DiskStorage(Path(get_settings().media_root))


__all__ = ["DiskStorage", "Storage", "StorageLimitExceeded", "get_storage"]