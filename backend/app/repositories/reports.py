from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Report, ReportStatus


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, report_id: int) -> Report | None:
        return await self.session.get(Report, report_id)

    def add(self, report: Report) -> None:
        self.session.add(report)

    async def list_by_status(
        self, status: ReportStatus, *, cursor: int | None, limit: int
    ) -> list[Report]:
        stmt = select(Report).where(Report.status == status)
        if status == ReportStatus.open:  # очередь: старые жалобы первыми
            if cursor is not None:
                stmt = stmt.where(Report.id > cursor)
            stmt = stmt.order_by(Report.id.asc())
        else:  # история: новые первыми
            if cursor is not None:
                stmt = stmt.where(Report.id < cursor)
            stmt = stmt.order_by(Report.id.desc())
        return list((await self.session.execute(stmt.limit(limit + 1))).scalars())

    async def resolve_open(
        self,
        *,
        handler_id: int,
        now: datetime,
        video_id: int | None = None,
        comment_id: int | None = None,
    ) -> None:
        """Закрывает все открытые жалобы на цель как resolved."""
        stmt = update(Report).where(Report.status == ReportStatus.open)
        if video_id is not None:
            stmt = stmt.where(Report.video_id == video_id)
        else:
            stmt = stmt.where(Report.comment_id == comment_id)
        await self.session.execute(
            stmt.values(status=ReportStatus.resolved, handled_by_id=handler_id, handled_at=now)
        )