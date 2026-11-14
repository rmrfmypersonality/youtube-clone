from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, VideoShare


class ShareRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def exists(self, video_id: int, user_id: int) -> bool:
        stmt = select(VideoShare.video_id).where(
            VideoShare.video_id == video_id, VideoShare.user_id == user_id
        )
        return (await self.session.execute(stmt)).first() is not None

    async def add(self, video_id: int, user_id: int) -> None:
        stmt = (
            insert(VideoShare)
            .values(video_id=video_id, user_id=user_id)
            .on_conflict_do_nothing()
        )
        await self.session.execute(stmt)

    async def remove(self, video_id: int, user_id: int) -> None:
        await self.session.execute(
            delete(VideoShare).where(
                VideoShare.video_id == video_id, VideoShare.user_id == user_id
            )
        )

    async def list_users(self, video_id: int) -> list[User]:
        stmt = (
            select(User)
            .join(VideoShare, VideoShare.user_id == User.id)
            .where(VideoShare.video_id == video_id)
            .order_by(VideoShare.created_at, User.id)
        )
        return list((await self.session.execute(stmt)).scalars().unique())