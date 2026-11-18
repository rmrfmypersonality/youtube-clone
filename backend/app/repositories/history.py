from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel, Video, VideoShare, VideoStatus, Visibility, WatchHistory


def visible_to(viewer_id: int, channel=Channel):
    """Что пользователь может открыть прямо сейчас. channel: сущность канала, уже в JOIN запроса
    (в подзапросах передают aliased(Channel))."""
    shared = select(VideoShare.video_id).where(VideoShare.user_id == viewer_id)
    listed = and_(
        Video.hidden_by_moderation.is_(False),
        channel.is_hidden.is_(False),
        or_(Video.visibility != Visibility.private, Video.id.in_(shared)),
    )
    return and_(Video.status == VideoStatus.ready, or_(Video.owner_id == viewer_id, listed))


class HistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, user_id: int, video_id: int) -> None:
        """Поднимает видео наверх истории. Коммитит вызывающий."""
        await self.session.execute(
            delete(WatchHistory).where(
                WatchHistory.user_id == user_id, WatchHistory.video_id == video_id
            )
        )
        # DO NOTHING: параллельный просмотр мог успеть вставить строку раньше
        await self.session.execute(
            insert(WatchHistory)
            .values(user_id=user_id, video_id=video_id)
            .on_conflict_do_nothing()
        )

    async def list_page(
        self, user_id: int, *, cursor: int | None, limit: int
    ) -> list[tuple[WatchHistory, Video, Channel]]:
        stmt = (
            select(WatchHistory, Video, Channel)
            .join(Video, Video.id == WatchHistory.video_id)
            .join(Channel, Channel.owner_id == Video.owner_id)
            .where(WatchHistory.user_id == user_id, visible_to(user_id))
            .order_by(WatchHistory.id.desc())
            .limit(limit + 1)
        )
        if cursor is not None:
            stmt = stmt.where(WatchHistory.id < cursor)
        rows = (await self.session.execute(stmt)).all()
        return [(r.WatchHistory, r.Video, r.Channel) for r in rows]

    async def remove(self, user_id: int, video_id: int) -> None:
        await self.session.execute(
            delete(WatchHistory).where(
                WatchHistory.user_id == user_id, WatchHistory.video_id == video_id
            )
        )

    async def clear(self, user_id: int) -> None:
        await self.session.execute(delete(WatchHistory).where(WatchHistory.user_id == user_id))