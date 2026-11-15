import os
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import quote

import anyio

from app.storage.base import Storage, StorageLimitExceeded

FLUSH_SIZE = 1024 * 1024  # пишем блоками по 1 МБ, а не по 64 КБ из сокета


class DiskStorage(Storage):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _resolve(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if path == self.root or not path.is_relative_to(self.root):
            raise ValueError("invalid storage key")
        return path

    def local_path(self, key: str, *, for_write: bool = False) -> Path:
        path = self._resolve(key)
        if for_write:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def internal_url(self, key: str) -> str:
        rel = self._resolve(key).relative_to(self.root).as_posix()
        return f"/media/{quote(rel)}"

    async def save_stream(
        self, key: str, chunks: AsyncIterator[bytes], *, max_bytes: int
    ) -> int:
        path = self.local_path(key, for_write=True)
        part = path.with_name(path.name + ".part")
        written = 0
        buf = bytearray()
        try:
            async with await anyio.open_file(part, "wb") as f:
                async for chunk in chunks:
                    written += len(chunk)
                    if written > max_bytes:
                        raise StorageLimitExceeded()
                    buf += chunk
                    if len(buf) >= FLUSH_SIZE:
                        await f.write(bytes(buf))
                        buf.clear()
                if buf:
                    await f.write(bytes(buf))
            os.replace(part, path)
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        return written

    async def delete(self, key: str) -> None:
        await anyio.Path(self._resolve(key)).unlink(missing_ok=True)

    async def delete_prefix(self, prefix: str) -> None:
        path = self._resolve(prefix)  # проверка на выход за root до любых действий
        await anyio.to_thread.run_sync(shutil.rmtree, path, True)