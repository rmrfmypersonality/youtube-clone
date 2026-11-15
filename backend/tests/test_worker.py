import asyncio
import shutil
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.time import utcnow
from app.models import Job, JobStatus, Video, VideoStatus
from app.repositories.jobs import JobRepository
from app.storage import get_storage
from worker import ffmpeg
from worker.processor import reclaim_stale, cleanup_pending, run_once

HEADERS = {"Content-Type": "application/octet-stream"}
VALID_HEAD = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 1024

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg не установлен")


async def upload(client, content) -> int:
    video = (await client.post("/api/videos", json={"title": "t", "visibility": "public"})).json()
    r = await client.put(f"/api/videos/{video['id']}/file", content=content, headers=HEADERS)
    assert r.status_code == 202, r.text
    return video["id"]


async def col(db, column, *where):
    return (await db.execute(select(column).where(*where))).scalar_one()


async def test_run_once_on_empty_queue():
    assert await run_once() is False


async def test_worker_processes_video(make_client, sample_video, db):
    alice = await make_client("alice")
    video_id = await upload(alice, sample_video)

    assert await run_once() is True

    body = (await alice.get(f"/api/videos/{video_id}")).json()
    assert body["status"] == "ready"
    assert 1.5 < body["duration_seconds"] < 2.5

    video = await db.get(Video, video_id)
    storage = get_storage()
    for key in (video.path_720, video.path_360, video.thumbnail_path):
        assert storage.local_path(key).stat().st_size > 0

    # Исходник 360p: апскейла до 720 нет
    info = await ffmpeg.probe(storage.local_path(video.path_720), timeout=30)
    assert info.height == 360
    assert await col(db, Job.status, Job.video_id == video_id) == JobStatus.done


@needs_ffmpeg
async def test_worker_fails_permanently_on_garbage(make_client, db):
    alice = await make_client("alice")
    video_id = await upload(alice, VALID_HEAD)  # magic bytes верные, внутри мусор

    assert await run_once() is True

    assert await col(db, Video.status, Video.id == video_id) == VideoStatus.failed
    assert await col(db, Job.status, Job.video_id == video_id) == JobStatus.failed
    assert await col(db, Job.attempts, Job.video_id == video_id) == 1  # повторов нет
    assert await col(db, Job.error, Job.video_id == video_id)


async def test_concurrent_claims_do_not_overlap(make_client):
    alice = await make_client("alice")
    await upload(alice, VALID_HEAD)
    await upload(alice, VALID_HEAD)

    async def claim():
        async with SessionLocal() as session:
            return await JobRepository(session).claim_next()

    a, b = await asyncio.gather(claim(), claim())
    assert a is not None and b is not None
    assert a.id != b.id
    assert a.attempts == b.attempts == 1
    assert await claim() is None


async def _make_running(db, video_id, *, locked_at, attempts):
    await db.execute(
        update(Job)
        .where(Job.video_id == video_id)
        .values(status=JobStatus.running, locked_at=locked_at, attempts=attempts)
    )
    await db.execute(update(Video).where(Video.id == video_id).values(status=VideoStatus.processing))
    await db.commit()


async def test_reclaim_requeues_stale_job(make_client, db):
    alice = await make_client("alice")
    video_id = await upload(alice, VALID_HEAD)
    await _make_running(db, video_id, locked_at=utcnow() - timedelta(hours=5), attempts=1)

    await reclaim_stale()

    assert await col(db, Job.status, Job.video_id == video_id) == JobStatus.queued
    assert await col(db, Video.status, Video.id == video_id) == VideoStatus.uploaded


async def test_reclaim_fails_job_after_max_attempts(make_client, db):
    alice = await make_client("alice")
    video_id = await upload(alice, VALID_HEAD)
    await _make_running(
        db, video_id, locked_at=utcnow() - timedelta(hours=5), attempts=get_settings().job_max_attempts
    )

    await reclaim_stale()

    assert await col(db, Job.status, Job.video_id == video_id) == JobStatus.failed
    assert await col(db, Video.status, Video.id == video_id) == VideoStatus.failed


async def test_reclaim_ignores_fresh_job(make_client, db):
    alice = await make_client("alice")
    video_id = await upload(alice, VALID_HEAD)
    await _make_running(db, video_id, locked_at=utcnow(), attempts=1)

    await reclaim_stale()

    assert await col(db, Job.status, Job.video_id == video_id) == JobStatus.running


async def test_cleanup_pending_removes_only_stale_pending(make_client, make_video, db):
    await make_client("alice")
    old = await make_video("alice", status=VideoStatus.pending)
    fresh = await make_video("alice", status=VideoStatus.pending)
    old_uploaded = await make_video("alice", status=VideoStatus.uploaded)
    long_ago = utcnow() - timedelta(hours=get_settings().pending_ttl_hours + 1)
    await db.execute(
        update(Video).where(Video.id.in_([old.id, old_uploaded.id])).values(created_at=long_ago)
    )
    await db.commit()

    await cleanup_pending()

    remaining = set((await db.execute(select(Video.id))).scalars())
    assert remaining == {fresh.id, old_uploaded.id}