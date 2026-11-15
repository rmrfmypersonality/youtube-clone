from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel, Video, VideoStatus, Visibility


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class VideoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, video_id: int) -> Video | None:
        return await self.session.get(Video, video_id)

    async def get_with_channel(self, video_id: int) -> tuple[Video, Channel] | None:
        stmt = (
            select(Video, Channel)
            .join(Channel, Channel.owner_id == Video.owner_id)
            .where(Video.id == video_id)
        )
        row = (await self.session.execute(stmt)).first()
        return (row.Video, row.Channel) if row else None

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

    async def increment_views(self, video_id: int) -> int | None:
        stmt = (
            update(Video)
            .where(Video.id == video_id)
            .values(views_count=Video.views_count + 1)
            .returning(Video.views_count)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_public(
        self, *, query: str | None, cursor: int | None, limit: int
    ) -> list[tuple[Video, Channel]]:
        """Публичная лента и поиск: только public + ready + не скрыто модерацией."""
        stmt = (
            select(Video, Channel)
            .join(Channel, Channel.owner_id == Video.owner_id)
            .where(
                Video.status == VideoStatus.ready,
                Video.visibility == Visibility.public,
                Video.hidden_by_moderation.is_(False),
            )
            .order_by(Video.id.desc())
            .limit(limit + 1)
        )
        if cursor is not None:
            stmt = stmt.where(Video.id < cursor)
        if query:
            # ILIKE по колонке, чтобы работал GIN-индекс pg_trgm; wildcard'ы пользователя экранируем
            stmt = stmt.where(Video.title.ilike(f"%{_escape_like(query)}%", escape="\\"))
        rows = (await self.session.execute(stmt)).all()
        return [(r.Video, r.Channel) for r in rows]