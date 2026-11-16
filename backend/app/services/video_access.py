from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models import Channel, User, Video, Visibility
from app.policies import videos as video_policy
from app.repositories.video_shares import ShareRepository
from app.repositories.videos import VideoRepository

NOT_FOUND = "Видео не найдено"


class VideoAccess:
    """Единая точка проверки «может ли пользователь видеть видео».
    Нет видео и нет прав выглядят одинаково: 404."""

    def __init__(self, session: AsyncSession) -> None:
        self.videos = VideoRepository(session)
        self.shares = ShareRepository(session)

    async def can_view(self, user: User | None, video: Video, channel: Channel) -> bool:
        is_shared = False
        if (
            user is not None
            and video.visibility == Visibility.private
            and not video_policy.is_owner(user, video)
        ):
            is_shared = await self.shares.exists(video.id, user.id)
        return video_policy.can_view_video(
            user, video, is_shared=is_shared, channel_hidden=channel.is_hidden
        )

    async def visible(self, user: User | None, video_id: int) -> tuple[Video, Channel]:
        found = await self.videos.get_with_channel(video_id)
        if found is None or not await self.can_view(user, *found):
            raise NotFound(NOT_FOUND)
        return found