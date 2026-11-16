from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Channel, Subscription, Video, VideoStatus, Visibility
from app.core.sql import escape_like

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
            self,
            *,
            query: str | None,
            cursor: int | None,
            limit: int,
            owner_id: int | None = None,
            subscriber_id: int | None = None,
    ) -> list[tuple[Video, Channel]]:
        """Публичная лента, поиск и видео канала: только public + ready + не скрыто модерацией."""
        stmt = (
            select(Video, Channel)
            .join(Channel, Channel.owner_id == Video.owner_id)
            .where(
                Video.status == VideoStatus.ready,
                Video.visibility == Visibility.public,
                Video.hidden_by_moderation.is_(False),
                Channel.is_hidden.is_(False),
            )
            .order_by(Video.id.desc())
            .limit(limit + 1)
        )
        if owner_id is not None:
            stmt = stmt.where(Video.owner_id == owner_id)
        if cursor is not None:
            stmt = stmt.where(Video.id < cursor)
        if query:
            # ILIKE по колонке, чтобы работал GIN-индекс pg_trgm; wildcard'ы пользователя экранируем
            stmt = stmt.where(Video.title.ilike(f"%{escape_like(query)}%", escape="\\"))

        if subscriber_id is not None:
            # alias обязателен: без него SQLAlchemy коррелирует подзапрос с Channel внешнего запроса
            followed = aliased(Channel)
            owners = (
                select(followed.owner_id)
                .join(Subscription, Subscription.channel_id == followed.id)
                .where(Subscription.subscriber_id == subscriber_id)
            )
            stmt = stmt.where(Video.owner_id.in_(owners))
        rows = (await self.session.execute(stmt)).all()
        return [(r.Video, r.Channel) for r in rows]

    async def list_by_owner(self, owner_id: int, *, cursor: int | None, limit: int) -> list[Video]:
        """Все видео владельца во всех статусах (для раздела «Мои видео»)."""
        stmt = select(Video).where(Video.owner_id == owner_id).order_by(Video.id.desc()).limit(limit + 1)
        if cursor is not None:
            stmt = stmt.where(Video.id < cursor)
        return list((await self.session.execute(stmt)).scalars())

    async def get_many(self, ids: set[int]) -> list[Video]:
        if not ids:
            return []
        return list((await self.session.execute(select(Video).where(Video.id.in_(ids)))).scalars())