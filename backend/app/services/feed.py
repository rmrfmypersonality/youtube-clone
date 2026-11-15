from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel, Video
from app.repositories.videos import VideoRepository
from app.schemas.auth import ChannelBrief
from app.schemas.videos import VideoCardOut, VideoPage


def _page(rows: list[tuple[Video, Channel]], limit: int) -> VideoPage:
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [
        VideoCardOut(
            id=v.id,
            title=v.title,
            duration_seconds=v.duration_seconds,
            views_count=v.views_count,
            created_at=v.created_at,
            channel=ChannelBrief.model_validate(ch),
        )
        for v, ch in rows
    ]
    return VideoPage(items=items, next_cursor=rows[-1][0].id if has_more else None)


class FeedService:
    def __init__(self, session: AsyncSession) -> None:
        self.videos = VideoRepository(session)

    async def home(self, *, cursor: int | None, limit: int) -> VideoPage:
        return _page(await self.videos.list_public(query=None, cursor=cursor, limit=limit), limit)

    async def search(self, q: str, *, cursor: int | None, limit: int) -> VideoPage:
        q = q.replace("\x00", "").strip()  # NUL Postgres не принимает, иначе был бы 500
        if not q:
            return VideoPage(items=[], next_cursor=None)
        return _page(await self.videos.list_public(query=q, cursor=cursor, limit=limit), limit)