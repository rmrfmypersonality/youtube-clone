from pathlib import Path

import pytest
from sqlalchemy import select, update

from app.core.config import get_settings
from app.models import Job, JobStatus, Role, User, Video, VideoStatus
from app.storage import get_storage

HEADERS = {"Content-Type": "application/octet-stream"}
VALID = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 1024


async def create_video(client, **overrides):
    r = await client.post("/api/videos", json={"title": "My video", **overrides})
    assert r.status_code == 201, r.text
    return r.json()


async def put_file(client, video_id, content):
    return await client.put(f"/api/videos/{video_id}/file", content=content, headers=HEADERS)


def stored_files() -> list[Path]:
    return [p for p in Path(get_settings().media_root).rglob("*") if p.is_file()]


async def test_create_requires_auth(client):
    assert (await client.post("/api/videos", json={"title": "x"})).status_code == 401


async def test_create_video_defaults(make_client):
    alice = await make_client("alice")
    body = await create_video(alice)
    assert body["status"] == "pending"
    assert body["visibility"] == "private"
    assert body["hidden_by_moderation"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 101},
        {"title": "ok", "visibility": "secret"},
        {"title": "ok", "description": "x" * 5001},
        {"title": "bad\x00title"},
    ],
)
async def test_create_validation(make_client, payload):
    alice = await make_client("alice")
    assert (await alice.post("/api/videos", json=payload)).status_code == 422


async def test_upload_valid_file(make_client, db):
    alice = await make_client("alice")
    video = await create_video(alice)

    r = await put_file(alice, video["id"], VALID)
    assert r.status_code == 202
    assert r.json()["status"] == "uploaded"

    row = await db.get(Video, video["id"])
    assert get_storage().local_path(row.original_path).read_bytes() == VALID
    job = (await db.execute(select(Job).where(Job.video_id == video["id"]))).scalar_one()
    assert job.status == JobStatus.queued


async def test_upload_requires_auth(make_client, client):
    alice = await make_client("alice")
    video = await create_video(alice)
    assert (await put_file(client, video["id"], VALID)).status_code == 401


@pytest.mark.parametrize(
    "content",
    [b"this is a text file, definitely not a video" * 10, b"", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100],
    ids=["text", "empty", "png"],
)
async def test_upload_rejects_non_video(make_client, db, content):
    alice = await make_client("alice")
    video = await create_video(alice)

    assert (await put_file(alice, video["id"], content)).status_code == 415
    assert (await db.get(Video, video["id"])).status == VideoStatus.pending
    assert stored_files() == []


async def test_upload_too_large_by_content_length(make_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    alice = await make_client("alice")
    video = await create_video(alice)

    r = await put_file(alice, video["id"], VALID + b"\x00" * (1024 * 1024))
    assert r.status_code == 413
    assert stored_files() == []


async def test_upload_too_large_in_stream(make_client, db, monkeypatch):
    """Без Content-Length (chunked) лимит всё равно срабатывает посреди потока."""
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    alice = await make_client("alice")
    video = await create_video(alice)

    async def body():
        yield VALID
        for _ in range(3):
            yield b"\x00" * (512 * 1024)

    r = await alice.put(f"/api/videos/{video['id']}/file", content=body(), headers=HEADERS)
    assert r.status_code == 413
    assert (await db.get(Video, video["id"])).status == VideoStatus.pending
    assert stored_files() == []


async def test_upload_twice_conflict(make_client):
    alice = await make_client("alice")
    video = await create_video(alice)
    assert (await put_file(alice, video["id"], VALID)).status_code == 202
    assert (await put_file(alice, video["id"], VALID)).status_code == 409


async def test_cannot_upload_to_foreign_video(make_client, db):
    alice, bob = await make_client("alice"), await make_client("bob")
    video = await create_video(alice)

    assert (await put_file(bob, video["id"], VALID)).status_code == 404
    assert (await db.get(Video, video["id"])).status == VideoStatus.pending
    assert stored_files() == []


async def test_admin_cannot_upload_file_for_others(make_client, db):
    alice, root = await make_client("alice"), await make_client("root")
    await db.execute(update(User).where(User.username == "root").values(role=Role.admin))
    await db.commit()
    video = await create_video(alice)
    assert (await put_file(root, video["id"], VALID)).status_code == 404


async def test_get_video_idor(make_client, client, db):
    alice, bob, root = await make_client("alice"), await make_client("bob"), await make_client("root")
    await db.execute(update(User).where(User.username == "root").values(role=Role.admin))
    await db.commit()
    video = await create_video(alice)
    url = f"/api/videos/{video['id']}"

    assert (await alice.get(url)).status_code == 200
    assert (await root.get(url)).status_code == 200
    assert (await bob.get(url)).status_code == 404  # не 403: не выдаём факт существования
    assert (await client.get(url)).status_code == 401
    assert (await alice.get("/api/videos/99999")).status_code == 404