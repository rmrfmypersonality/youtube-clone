from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.models import User
from app.policies import roles as role_policy
from app.repositories.users import UserRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user_optional(
    session: SessionDep,
    access_token: Annotated[str | None, Cookie()] = None,
) -> User | None:
    if not access_token:
        return None
    user_id = decode_access_token(access_token)
    if user_id is None:
        return None
    user = await UserRepository(session).get(user_id)
    # Роль и is_active берём из БД на каждом запросе: блокировка и смена роли действуют сразу
    if user is None or not user.is_active:
        return None
    return user


OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


async def get_current_user(user: OptionalUser) -> User:
    if user is None:
        raise Unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_moderator(user: CurrentUser) -> User:
    if not role_policy.can_moderate(user):
        raise Forbidden()
    return user


async def require_admin(user: CurrentUser) -> User:
    if not role_policy.is_admin(user):
        raise Forbidden()
    return user


ModeratorUser = Annotated[User, Depends(require_moderator)]
AdminUser = Annotated[User, Depends(require_admin)]