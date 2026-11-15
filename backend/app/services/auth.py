import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import Conflict, Forbidden, Unauthorized
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.time import utcnow
from app.models import Channel, RefreshToken, User
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.repositories.channels import ChannelRepository
from app.schemas.auth import LoginIn, RegisterIn

INVALID_SESSION = "Сессия недействительна"


@dataclass
class AuthResult:
    user: User
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.channels = ChannelRepository(session)
        self.session = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)

    async def register(self, data: RegisterIn) -> AuthResult:
        if await self.users.get_by_email(data.email):
            raise Conflict("Этот email уже занят")
        if await self.users.get_by_username(data.username):
            raise Conflict("Это имя пользователя уже занято")
        if await self.channels.get_by_handle(data.username):  # handle мог быть занят сменой
            raise Conflict("Это имя пользователя уже занято")

        user = User(
            email=data.email,
            username=data.username,
            password_hash=await run_in_threadpool(hash_password, data.password),
            channel=Channel(handle=data.username, name=data.username),
        )
        self.users.add(user)
        try:
            await self.session.flush()
        except IntegrityError:  # гонка двух регистраций
            await self.session.rollback()
            raise Conflict("Email или имя пользователя уже заняты")

        result = self._issue(user, family_id=uuid.uuid4())
        await self.session.commit()
        return result

    async def login(self, data: LoginIn) -> AuthResult:
        user = await self.users.get_by_email(data.email)
        password_hash = user.password_hash if user else DUMMY_HASH
        password_ok = await run_in_threadpool(verify_password, password_hash, data.password)
        if user is None or not password_ok:
            raise Unauthorized("Неверный email или пароль")
        if not user.is_active:
            raise Forbidden("Аккаунт заблокирован")

        result = self._issue(user, family_id=uuid.uuid4())
        await self.session.commit()
        return result

    async def refresh(self, raw_token: str) -> AuthResult:
        now = utcnow()
        token = await self.tokens.get_by_hash(hash_refresh_token(raw_token), for_update=True)
        if token is None:
            raise Unauthorized(INVALID_SESSION)
        if token.revoked_at is not None:
            # Повторное предъявление отозванного токена: считаем утечкой и гасим всю цепочку
            await self.tokens.revoke_family(token.family_id, now)
            await self.session.commit()
            raise Unauthorized(INVALID_SESSION)
        if token.expires_at <= now:
            raise Unauthorized(INVALID_SESSION)

        user = await self.users.get(token.user_id)
        if user is None or not user.is_active:
            raise Unauthorized(INVALID_SESSION)

        token.revoked_at = now
        result = self._issue(user, family_id=token.family_id)
        await self.session.commit()
        return result

    async def logout(self, raw_token: str) -> None:
        token = await self.tokens.get_by_hash(hash_refresh_token(raw_token))
        if token is not None:
            await self.tokens.revoke_family(token.family_id, utcnow())
            await self.session.commit()

    def _issue(self, user: User, family_id: uuid.UUID) -> AuthResult:
        settings = get_settings()
        raw = generate_refresh_token()
        self.tokens.add(
            RefreshToken(
                user_id=user.id,
                family_id=family_id,
                token_hash=hash_refresh_token(raw),
                expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
            )
        )
        return AuthResult(user=user, access_token=create_access_token(user.id), refresh_token=raw)