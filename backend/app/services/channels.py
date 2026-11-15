from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, Conflict, NotFound
from app.models import Channel, User
from app.repositories.channels import ChannelRepository
from app.repositories.subscriptions import SubscriptionRepository
from app.repositories.users import UserRepository
from app.repositories.videos import VideoRepository
from app.schemas.channels import ChannelOut, ChannelUpdate, SubscriptionOut
from app.schemas.videos import VideoPage
from app.services.feed import video_page

CHANNEL_NOT_FOUND = "Канал не найден"


class ChannelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.channels = ChannelRepository(session)
        self.subs = SubscriptionRepository(session)
        self.users = UserRepository(session)
        self.videos = VideoRepository(session)

    async def _get(self, handle: str) -> Channel:
        channel = await self.channels.get_by_handle(handle)
        if channel is None:
            raise NotFound(CHANNEL_NOT_FOUND)
        return channel

    async def _out(self, channel: Channel, viewer: User | None) -> ChannelOut:
        is_subscribed = False
        if viewer is not None:
            is_subscribed = await self.subs.exists(viewer.id, channel.id)
        return ChannelOut(
            id=channel.id,
            handle=channel.handle,
            name=channel.name,
            description=channel.description,
            created_at=channel.created_at,
            subscribers_count=await self.subs.count(channel.id),
            videos_count=await self.channels.count_public_videos(channel.owner_id),
            is_subscribed=is_subscribed,
            is_owner=viewer is not None and viewer.id == channel.owner_id,
        )

    async def get(self, viewer: User | None, handle: str) -> ChannelOut:
        return await self._out(await self._get(handle), viewer)

    async def update_mine(self, user: User, data: ChannelUpdate) -> ChannelOut:
        channel = user.channel
        if data.handle is not None and data.handle != channel.handle:
            other = await self.channels.get_by_handle(data.handle)
            name_owner = await self.users.get_by_username(data.handle)
            if (other is not None and other.id != channel.id) or (
                name_owner is not None and name_owner.id != user.id
            ):
                raise Conflict("Этот handle уже занят")
            channel.handle = data.handle
        if data.name is not None:
            channel.name = data.name
        if data.description is not None:
            channel.description = data.description
        try:
            await self.session.commit()
        except IntegrityError:  # гонка двух смен handle
            await self.session.rollback()
            raise Conflict("Этот handle уже занят") from None
        return await self._out(channel, user)

    async def list_videos(self, handle: str, *, cursor: int | None, limit: int) -> VideoPage:
        channel = await self._get(handle)
        rows = await self.videos.list_public(
            query=None, cursor=cursor, limit=limit, owner_id=channel.owner_id
        )
        return video_page(rows, limit)

    async def subscribe(self, user: User, handle: str) -> SubscriptionOut:
        channel = await self._get(handle)
        if channel.owner_id == user.id:
            raise AppError("Нельзя подписаться на свой канал")
        await self.subs.add(user.id, channel.id)
        await self.session.commit()
        return SubscriptionOut(subscribed=True, subscribers_count=await self.subs.count(channel.id))

    async def unsubscribe(self, user: User, handle: str) -> SubscriptionOut:
        channel = await self._get(handle)
        await self.subs.remove(user.id, channel.id)
        await self.session.commit()
        return SubscriptionOut(subscribed=False, subscribers_count=await self.subs.count(channel.id))