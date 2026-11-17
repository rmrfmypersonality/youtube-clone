from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel, Video
from app.repositories.videos import VideoRepository
from app.schemas.auth import ChannelBrief
from app.schemas.videos import VideoCardOut, VideoPage


def to_card(video: Video, channel: Channel) -> VideoCardOut:
    return VideoCardOut(
        id=video.id,
        title=video.title,
        duration_seconds=video.duration_seconds,
        views_count=video.views_count,
        created_at=video.created_at,
        channel=ChannelBrief.model_validate(channel),
    )


def video_page(rows: list[tuple[Video, Channel]], limit: int) -> VideoPage:
    has_more = len(rows) > limit  # репозиторий берёт limit + 1
    rows = rows[:limit]
    return VideoPage(
        items=[to_card(v, ch) for v, ch in rows],
        next_cursor=rows[-1][0].id if has_more else None,
    )


class FeedService:
    def __init__(self, session: AsyncSession) -> None:
        self.videos = VideoRepository(session)

    async def home(
            self, *, cursor: int | None, limit: int, category: str | None = None
    ) -> VideoPage:
        rows = await self.videos.list_public(
            query=None, cursor=cursor, limit=limit, category_slug=category
        )
        return video_page(rows, limit)

    async def search(self, q: str, *, cursor: int | None, limit: int) -> VideoPage:
        q = q.replace("\x00", "").strip()  # NUL Postgres не принимает, иначе был бы 500
        if not q:
            return VideoPage(items=[], next_cursor=None)
        rows = await self.videos.list_public(query=q, cursor=cursor, limit=limit)
        return video_page(rows, limit)

    async def subscriptions(self, user_id: int, *, cursor: int | None, limit: int) -> VideoPage:
        rows = await self.videos.list_public(
            query=None, cursor=cursor, limit=limit, subscriber_id=user_id
        )
        return video_page(rows, limit)