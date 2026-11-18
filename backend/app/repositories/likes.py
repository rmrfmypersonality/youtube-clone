from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel, Like, Video
from app.repositories.history import visible_to


class LikeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set(self, user_id: int, video_id: int, value: int) -> None:
        if await self.get_value(user_id, video_id) == value:
            return  # повтор не двигает видео в «Понравившихся»
        # Строка пересоздаётся: новый id поднимает видео наверх списка
        await self.remove(user_id, video_id)
        await self.session.execute(
            insert(Like)
            .values(user_id=user_id, video_id=video_id, value=value)
            .on_conflict_do_nothing()
        )

    async def remove(self, user_id: int, video_id: int) -> None:
        await self.session.execute(
            delete(Like).where(Like.user_id == user_id, Like.video_id == video_id)
        )

    async def count_likes(self, video_id: int) -> int:
        stmt = select(func.count()).select_from(Like).where(
            Like.video_id == video_id, Like.value == 1
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def get_value(self, user_id: int, video_id: int) -> int:
        stmt = select(Like.value).where(Like.user_id == user_id, Like.video_id == video_id)
        return (await self.session.execute(stmt)).scalar_one_or_none() or 0

    def _liked_query(self, user_id: int, *columns):
        return (
            select(*columns)
            .select_from(Like)
            .join(Video, Video.id == Like.video_id)
            .join(Channel, Channel.owner_id == Video.owner_id)
            .where(Like.user_id == user_id, Like.value == 1, visible_to(user_id))
        )

    async def list_liked(
        self, user_id: int, *, cursor: int | None, limit: int
    ) -> list[tuple[Like, Video, Channel]]:
        stmt = self._liked_query(user_id, Like, Video, Channel).order_by(Like.id.desc()).limit(limit + 1)
        if cursor is not None:
            stmt = stmt.where(Like.id < cursor)
        return [(r.Like, r.Video, r.Channel) for r in (await self.session.execute(stmt)).all()]

    async def random_liked(self, user_id: int) -> int | None:
        stmt = self._liked_query(user_id, Like.video_id).order_by(func.random()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()