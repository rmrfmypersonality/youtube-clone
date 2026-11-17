from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models import User
from app.repositories.notifications import NotificationRepository
from app.schemas.notifications import NotificationCount, NotificationItem, NotificationPage
from app.services.feed import to_card

COUNT_CAP = 100


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NotificationRepository(session)

    async def count(self, user: User) -> NotificationCount:
        n = await self.repo.count_new(user.id, user.notifications_seen_at, COUNT_CAP)
        return NotificationCount(count=n)

    async def list(self, user: User, *, cursor: int | None, limit: int) -> NotificationPage:
        rows = await self.repo.list_page(user.id, cursor=cursor, limit=limit)
        has_more = len(rows) > limit  # репозиторий берёт limit + 1
        rows = rows[:limit]
        return NotificationPage(
            items=[
                NotificationItem(**to_card(v, ch).model_dump(), published_at=v.published_at)
                for v, ch in rows
            ],
            next_cursor=rows[-1][0].id if has_more else None,
            seen_at=user.notifications_seen_at,
        )

    async def mark_seen(self, user: User) -> None:
        await self.repo.mark_seen(user.id, utcnow())
        await self.session.commit()