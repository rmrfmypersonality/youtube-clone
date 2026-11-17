from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.history import HistoryRepository
from app.schemas.history import HistoryPage
from app.services.feed import to_card


class HistoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.history = HistoryRepository(session)

    async def list(self, user: User, *, cursor: int | None, limit: int) -> HistoryPage:
        rows = await self.history.list_page(user.id, cursor=cursor, limit=limit)
        has_more = len(rows) > limit  # репозиторий берёт limit + 1
        rows = rows[:limit]
        return HistoryPage(
            items=[to_card(video, channel) for _, video, channel in rows],
            next_cursor=rows[-1][0].id if has_more else None,
        )

    async def remove(self, user: User, video_id: int) -> None:
        await self.history.remove(user.id, video_id)
        await self.session.commit()

    async def clear(self, user: User) -> None:
        await self.history.clear(user.id)
        await self.session.commit()