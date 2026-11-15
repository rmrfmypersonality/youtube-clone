from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def exists(self, user_id: int, channel_id: int) -> bool:
        stmt = select(Subscription.channel_id).where(
            Subscription.subscriber_id == user_id, Subscription.channel_id == channel_id
        )
        return (await self.session.execute(stmt)).first() is not None

    async def add(self, user_id: int, channel_id: int) -> None:
        stmt = (
            insert(Subscription)
            .values(subscriber_id=user_id, channel_id=channel_id)
            .on_conflict_do_nothing()
        )
        await self.session.execute(stmt)

    async def remove(self, user_id: int, channel_id: int) -> None:
        await self.session.execute(
            delete(Subscription).where(
                Subscription.subscriber_id == user_id, Subscription.channel_id == channel_id
            )
        )

    async def count(self, channel_id: int) -> int:
        stmt = select(func.count()).select_from(Subscription).where(
            Subscription.channel_id == channel_id
        )
        return (await self.session.execute(stmt)).scalar_one()