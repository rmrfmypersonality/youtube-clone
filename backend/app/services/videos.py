import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import Conflict, NotFound, PayloadTooLarge, UnsupportedMedia
from app.models import Job, User, Video, VideoStatus
from app.policies import videos as video_policy
from app.repositories.jobs import JobRepository
from app.repositories.videos import VideoRepository
from app.schemas.videos import VideoCreate
from app.services.video_files import HEAD_SIZE, sniff_container
from app.storage import Storage, StorageLimitExceeded

NOT_FOUND = "Видео не найдено"


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

    async def get_manageable(self, user: User, video_id: int) -> Video:
        # Пока видят только владелец и админ. На этапе 4 заменим на can_view_video.
        video = await self.videos.get(video_id)
        if video is None or not video_policy.can_edit_video(user, video):
            raise NotFound(NOT_FOUND)
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