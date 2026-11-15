from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict
from app.models import User, VideoStatus
from app.repositories.likes import LikeRepository
from app.schemas.reactions import ReactionOut
from app.services.video_access import VideoAccess


class ReactionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.access = VideoAccess(session)
        self.likes = LikeRepository(session)

    async def set(self, user: User, video_id: int, value: int) -> ReactionOut:
        video, _ = await self.access.visible(user, video_id)
        if video.status != VideoStatus.ready:
            raise Conflict("Видео ещё не готово")
        if value == 0:
            await self.likes.remove(user.id, video.id)
        else:
            await self.likes.set(user.id, video.id, value)
        await self.session.commit()
        return ReactionOut(likes_count=await self.likes.count_likes(video.id), my_reaction=value)