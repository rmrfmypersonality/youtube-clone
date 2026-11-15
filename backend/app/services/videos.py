import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AppError,
    Conflict,
    NotFound,
    PayloadTooLarge,
    UnsupportedMedia,
)
from app.models import Channel, Job, User, Video, VideoStatus
from app.policies import videos as video_policy
from app.repositories.jobs import JobRepository
from app.repositories.likes import LikeRepository
from app.repositories.users import UserRepository
from app.repositories.video_shares import ShareRepository
from app.repositories.videos import VideoRepository
from app.schemas.auth import ChannelBrief
from app.schemas.videos import Quality, VideoCreate, VideoDetailOut, VideoOut
from app.services.video_access import NOT_FOUND, VideoAccess
from app.services.video_files import HEAD_SIZE, sniff_container
from app.storage import Storage, StorageLimitExceeded


async def _validated(stream: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """Пропускает поток дальше, но сначала проверяет magic bytes по первым байтам."""
    head = bytearray()
    checked = False
    async for chunk in stream:
        if checked:
            yield chunk
            continue
        head += chunk
        if len(head) >= HEAD_SIZE:
            if sniff_container(bytes(head)) is None:
                raise UnsupportedMedia("Поддерживаются только MP4, MOV, WebM и MKV")
            checked = True
            yield bytes(head)
    if not checked:
        raise UnsupportedMedia("Файл пуст или не является видео")


class VideoService:
    def __init__(self, session: AsyncSession, storage: Storage) -> None:
        self.session = session
        self.storage = storage
        self.videos = VideoRepository(session)
        self.jobs = JobRepository(session)
        self.shares = ShareRepository(session)
        self.users = UserRepository(session)
        self.likes = LikeRepository(session)
        self.access = VideoAccess(session)

    # --- создание и загрузка ---

    async def create(self, user: User, data: VideoCreate) -> Video:
        video = Video(
            owner_id=user.id,
            title=data.title,
            description=data.description,
            visibility=data.visibility,
        )
        self.videos.add(video)
        await self.session.commit()
        await self.session.refresh(video)
        return video

    async def upload_file(
        self,
        user: User,
        video_id: int,
        stream: AsyncIterator[bytes],
        content_length: int | None,
    ) -> Video:
        max_bytes = get_settings().max_upload_bytes

        video = await self.videos.get(video_id)
        if video is None or not video_policy.can_upload_video_file(user, video):
            raise NotFound(NOT_FOUND)
        if video.status != VideoStatus.pending:
            raise Conflict("Файл для этого видео уже загружен")
        if content_length is not None and content_length > max_bytes:
            raise PayloadTooLarge()

        # Закрываем транзакцию, чтобы не держать соединение с БД всё время загрузки
        await self.session.commit()

        key = f"originals/{uuid.uuid4().hex}"  # имя генерируем сами, от клиента ничего не берём
        try:
            await self.storage.save_stream(key, _validated(stream), max_bytes=max_bytes)
        except StorageLimitExceeded:
            raise PayloadTooLarge() from None

        try:
            if not await self.videos.mark_uploaded(video_id, key):
                raise Conflict("Файл для этого видео уже загружен")
            self.jobs.add(Job(video_id=video_id))
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            await self.storage.delete(key)
            raise

        await self.session.refresh(video)
        return video

    # --- просмотр ---

    async def _visible(self, user: User | None, video_id: int) -> tuple[Video, Channel]:
        return await self.access.visible(user, video_id)

    async def get_visible(self, user: User | None, video_id: int) -> VideoDetailOut:
        video, channel = await self._visible(user, video_id)
        likes_count = await self.likes.count_likes(video.id)
        my_reaction = await self.likes.get_value(user.id, video.id) if user else 0
        return VideoDetailOut(
            **VideoOut.model_validate(video).model_dump(),
            channel=ChannelBrief.model_validate(channel),
            likes_count=likes_count,
            my_reaction=my_reaction,
        )

    async def stream_target(self, user: User | None, video_id: int, quality: Quality) -> str:
        video, _ = await self._visible(user, video_id)
        key = video.path_720 if quality == "720" else video.path_360
        if video.status != VideoStatus.ready or not key:
            raise NotFound("Файл видео недоступен")
        return self.storage.internal_url(key)

    async def thumbnail_target(self, user: User | None, video_id: int) -> str:
        video, _ = await self._visible(user, video_id)
        if video.status != VideoStatus.ready or not video.thumbnail_path:
            raise NotFound("Превью недоступно")
        return self.storage.internal_url(video.thumbnail_path)

    async def record_view(self, user: User | None, video_id: int) -> int:
        video, _ = await self._visible(user, video_id)
        if video.status != VideoStatus.ready:
            raise Conflict("Видео ещё не готово")
        count = await self.videos.increment_views(video.id)
        await self.session.commit()
        return count or 0

    # --- доступ к приватным видео ---

    async def _owned(self, user: User, video_id: int) -> Video:
        video = await self.videos.get(video_id)
        if video is None or not video_policy.can_manage_shares(user, video):
            raise NotFound(NOT_FOUND)
        return video

    async def list_shares(self, user: User, video_id: int) -> list[User]:
        video = await self._owned(user, video_id)
        return await self.shares.list_users(video.id)

    async def add_share(self, user: User, video_id: int, username: str) -> User:
        video = await self._owned(user, video_id)
        target = await self.users.get_by_username(username)
        if target is None or not target.is_active:
            raise NotFound("Пользователь не найден")
        if target.id == user.id:
            raise AppError("Нельзя выдать доступ самому себе")
        await self.shares.add(video.id, target.id)
        await self.session.commit()
        return target

    async def remove_share(self, user: User, video_id: int, target_user_id: int) -> None:
        video = await self._owned(user, video_id)
        await self.shares.remove(video.id, target_user_id)
        await self.session.commit()