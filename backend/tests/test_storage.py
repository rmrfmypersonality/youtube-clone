import pytest

from app.storage import DiskStorage, StorageLimitExceeded


async def gen(*chunks: bytes):
    for c in chunks:
        yield c


async def test_save_stream_writes_file(tmp_path):
    storage = DiskStorage(tmp_path)
    size = await storage.save_stream("a/b/file.bin", gen(b"abc", b"def"), max_bytes=100)
    assert size == 6
    assert (tmp_path / "a/b/file.bin").read_bytes() == b"abcdef"


async def test_limit_exceeded_leaves_nothing(tmp_path):
    storage = DiskStorage(tmp_path)
    with pytest.raises(StorageLimitExceeded):
        await storage.save_stream("f.bin", gen(b"x" * 60, b"x" * 60), max_bytes=100)
    assert list(tmp_path.iterdir()) == []


async def test_error_in_stream_removes_partial_file(tmp_path):
    async def broken():
        yield b"abc"
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await DiskStorage(tmp_path).save_stream("f.bin", broken(), max_bytes=100)
    assert list(tmp_path.iterdir()) == []


async def test_delete_missing_file_is_noop(tmp_path):
    await DiskStorage(tmp_path).delete("nope.bin")


@pytest.mark.parametrize("key", ["../evil", "/etc/passwd", "a/../../evil", ""])
def test_path_traversal_rejected(tmp_path, key):
    with pytest.raises(ValueError):
        DiskStorage(tmp_path).local_path(key)