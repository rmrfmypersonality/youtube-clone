from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models import Job, JobStatus


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, job: Job) -> None:
        self.session.add(job)

    async def claim_next(self) -> Job | None:
        """Берёт одну задачу из очереди. SKIP LOCKED: параллельные воркеры не пересекаются."""
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.queued)
            .order_by(Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = (await self.session.execute(stmt)).scalar_one_or_none()
        if job is None:
            return None
        job.status = JobStatus.running
        job.locked_at = utcnow()
        job.attempts += 1
        await self.session.commit()
        return job

    async def list_stale(self, stale_before: datetime) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.running, Job.locked_at < stale_before)
            .with_for_update(skip_locked=True)
        )
        return list((await self.session.execute(stmt)).scalars())