import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, update

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.time import utcnow
from app.models import Job, JobStatus, Video, VideoStatus
from app.repositories.jobs import JobRepository
from app.storage import get_storage
from worker import ffmpeg
from worker.ffmpeg import PermanentError

log = logging.getLogger("worker")


async def _heartbeat(job_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(update(Job).where(Job.id == job_id).values(locked_at=utcnow()))
        await session.commit()


async def _process(job: Job) -> None:
    settings = get_settings()
    storage = get_storage()
    timeout = settings.ffmpeg_step_timeout_seconds

    async with SessionLocal() as session:
        video = await session.get(Video, job.video_id)
        if video is None or not video.original_path:
            raise PermanentError("Видео или исходный файл не найдены")
        video.status = VideoStatus.processing
        await session.commit()
        video_id, original = video.id, video.original_path

    src = storage.local_path(original)
    info = await ffmpeg.probe(src, timeout)
    await _heartbeat(job.id)

    base = f"videos/{video_id}"
    key_720, key_360, key_thumb = f"{base}/720.mp4", f"{base}/360.mp4", f"{base}/thumb.jpg"

    await ffmpeg.transcode(src, storage.local_path(key_720, for_write=True), 720, timeout)
    await _heartbeat(job.id)
    await ffmpeg.transcode(src, storage.local_path(key_360, for_write=True), 360, timeout)
    await _heartbeat(job.id)
    await ffmpeg.thumbnail(
        src, storage.local_path(key_thumb, for_write=True), min(info.duration * 0.25, 5.0), timeout
    )

    async with SessionLocal() as session:
        video = await session.get(Video, video_id)
        db_job = await session.get(Job, job.id)
        orphaned = video is None  # видео удалили, пока шла обработка
        if video is not None:
            video.path_720, video.path_360, video.thumbnail_path = key_720, key_360, key_thumb
            video.duration_seconds = info.duration
            video.status = VideoStatus.ready
        if db_job is not None:
            db_job.status = JobStatus.done
            db_job.error = None
            db_job.locked_at = None
        await session.commit()
    if orphaned:
        await storage.delete_prefix(base)


async def _fail_or_retry(job: Job, error: str, *, retry: bool) -> None:
    max_attempts = get_settings().job_max_attempts
    async with SessionLocal() as session:
        db_job = await session.get(Job, job.id)
        video = await session.get(Video, job.video_id)
        if db_job is None:
            if db_job is None:  # видео удалили во время обработки, подчищаем недописанное
                await get_storage().delete_prefix(f"videos/{job.video_id}")
                return
        db_job.error = error[:2000]
        db_job.locked_at = None
        if retry and db_job.attempts < max_attempts:
            db_job.status = JobStatus.queued
            if video is not None:
                video.status = VideoStatus.uploaded
        else:
            db_job.status = JobStatus.failed
            if video is not None:
                video.status = VideoStatus.failed
        await session.commit()


async def _release(job: Job) -> None:
    """Воркер останавливают: возвращаем задачу в очередь, попытку не списываем."""
    async with SessionLocal() as session:
        db_job = await session.get(Job, job.id)
        video = await session.get(Video, job.video_id)
        if db_job is not None:
            db_job.status = JobStatus.queued
            db_job.locked_at = None
            db_job.attempts = max(0, db_job.attempts - 1)
        if video is not None:
            video.status = VideoStatus.uploaded
        await session.commit()


async def run_once() -> bool:
    """Обрабатывает одну задачу. False, если очередь пуста."""
    async with SessionLocal() as session:
        job = await JobRepository(session).claim_next()
    if job is None:
        return False

    log.info("job %s (video %s), попытка %s", job.id, job.video_id, job.attempts)
    try:
        await _process(job)
        log.info("job %s: готово", job.id)
    except asyncio.CancelledError:
        await _release(job)
        raise
    except PermanentError as e:
        log.warning("job %s: файл отклонён: %s", job.id, e)
        await _fail_or_retry(job, str(e), retry=False)
    except Exception as e:
        log.exception("job %s: ошибка обработки", job.id)
        await _fail_or_retry(job, str(e), retry=True)
    return True


async def reclaim_stale() -> None:
    """Задачи, у которых давно не обновлялся locked_at (воркер умер): в очередь или в failed."""
    settings = get_settings()
    stale_before = utcnow() - timedelta(seconds=settings.job_stale_seconds)
    async with SessionLocal() as session:
        for job in await JobRepository(session).list_stale(stale_before):
            video = await session.get(Video, job.video_id)
            job.locked_at = None
            if job.attempts >= settings.job_max_attempts:
                job.status = JobStatus.failed
                job.error = "Превышено время обработки"
                if video is not None:
                    video.status = VideoStatus.failed
            else:
                job.status = JobStatus.queued
                if video is not None:
                    video.status = VideoStatus.uploaded
            log.warning("job %s: зависшая задача, статус -> %s", job.id, job.status.value)
        await session.commit()


async def cleanup_pending() -> None:
    """Записи, для которых файл так и не загрузили (закрыли вкладку), удаляем через сутки."""
    cutoff = utcnow() - timedelta(hours=get_settings().pending_ttl_hours)
    async with SessionLocal() as session:
        result = await session.execute(
            delete(Video).where(Video.status == VideoStatus.pending, Video.created_at < cutoff)
        )
        await session.commit()
    if result.rowcount:
        log.info("Удалено %s видео без загруженного файла", result.rowcount)