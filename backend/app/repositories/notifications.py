from datetime import datetime

from sqlalchemy import Select, and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel, Subscription, User, Video, VideoStatus, Visibility


def _query(user_id: int, *columns) -> Select:
    """Видео подписок, ставшие публичными после самой подписки."""
    return (
        select(*columns)
        .select_from(Video)
        .join(Channel, Channel.owner_id == Video.owner_id)
        .join(
            Subscription,
            and_(Subscription.channel_id == Channel.id, Subscription.subscriber_id == user_id),
        )
        .where(
            Video.status == VideoStatus.ready,
            Video.visibility == Visibility.public,
            Video.hidden_by_moderation.is_(False),
            Channel.is_hidden.is_(False),
            Video.published_at >= Subscription.created_at,
        )
    )


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_new(self, user_id: int, seen_at: datetime, cap: int) -> int:
        inner = _query(user_id, Video.id).where(Video.published_at > seen_at).limit(cap)
        stmt = select(func.count()).select_from(inner.subquery())
        return (await self.session.execute(stmt)).scalar_one()

    async def list_page(
        self, user_id: int, *, cursor: int | None, limit: int
    ) -> list[tuple[Video, Channel]]:
        stmt = _query(user_id, Video, Channel).order_by(Video.id.desc()).limit(limit + 1)
        if cursor is not None:
            stmt = stmt.where(Video.id < cursor)
        return [(r.Video, r.Channel) for r in (await self.session.execute(stmt)).all()]

    async def mark_seen(self, user_id: int, now: datetime) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(notifications_seen_at=now)
        )