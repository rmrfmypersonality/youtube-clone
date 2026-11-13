from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Video, VideoStatus


class VideoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, video_id: int) -> Video | None:
        return await self.session.get(Video, video_id)

    def add(self, video: Video) -> None:
        self.session.add(video)

    async def mark_uploaded(self, video_id: int, original_path: str) -> bool:
        """Атомарно pending -> uploaded. False, если кто-то успел раньше (гонка двух загрузок)."""
        stmt = (
            update(Video)
            .where(Video.id == video_id, Video.status == VideoStatus.pending)
            .values(status=VideoStatus.uploaded, original_path=original_path)
            .returning(Video.id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None