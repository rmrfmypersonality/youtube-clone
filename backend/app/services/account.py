import logging

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, Forbidden
from app.core.security import verify_password
from app.models import Role, User
from app.repositories.users import UserRepository
from app.repositories.videos import VideoRepository
from app.storage import Storage

log = logging.getLogger(__name__)


class AccountService:
    def __init__(self, session: AsyncSession, storage: Storage) -> None:
        self.session = session
        self.storage = storage
        self.users = UserRepository(session)
        self.videos = VideoRepository(session)

    async def delete(self, user: User, password: str) -> None:
        ok = await run_in_threadpool(verify_password, user.password_hash, password)
        if not ok:
            raise Forbidden("Неверный пароль")  # не 401: фронт на 401 начнёт обновлять токен
        if user.role == Role.admin and not await self.users.has_other_active_admin(user.id):
            raise Conflict("Нельзя удалить единственного администратора")

        refs = await self.videos.storage_refs(user.id)
        # Канал, видео, комментарии, лайки, плейлисты, подписки и токены удаляет каскад в БД
        await self.session.delete(user)
        await self.session.commit()

        # Файлы чистим после коммита: сбой здесь не должен откатывать удаление аккаунта
        for video_id, original in refs:
            try:
                if original:
                    await self.storage.delete(original)
                await self.storage.delete_prefix(f"videos/{video_id}")
            except Exception:
                log.exception("Не удалось удалить файлы видео %s", video_id)