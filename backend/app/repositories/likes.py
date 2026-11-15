from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Like


class LikeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set(self, user_id: int, video_id: int, value: int) -> None:
        stmt = (
            insert(Like)
            .values(user_id=user_id, video_id=video_id, value=value)
            .on_conflict_do_update(
                index_elements=["user_id", "video_id"], set_={"value": value}
            )
        )
        await self.session.execute(stmt)

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