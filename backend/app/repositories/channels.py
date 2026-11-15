from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel, Video, VideoStatus, Visibility


class ChannelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_handle(self, handle: str) -> Channel | None:
        result = await self.session.execute(select(Channel).where(Channel.handle == handle))
        return result.scalar_one_or_none()

    async def count_public_videos(self, owner_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Video)
            .where(
                Video.owner_id == owner_id,
                Video.status == VideoStatus.ready,
                Video.visibility == Visibility.public,
                Video.hidden_by_moderation.is_(False),
            )
        )
        return (await self.session.execute(stmt)).scalar_one()