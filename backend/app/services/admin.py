from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFound
from app.core.time import utcnow
from app.models import User
from app.policies import roles as role_policy
from app.repositories.audit import AuditRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.schemas.admin import (
    AuditOut,
    AuditPage,
    UserAdminOut,
    UserAdminPage,
    UserAdminUpdate,
)
from app.schemas.moderation import UserBrief


def _user_out(user: User) -> UserAdminOut:
    return UserAdminOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        channel_handle=user.channel.handle,
    )


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)
        self.audit = AuditRepository(session)

    async def list_users(self, *, q: str | None, cursor: int | None, limit: int) -> UserAdminPage:
        q = (q or "").replace("\x00", "").strip()  # NUL Postgres не принимает
        rows = await self.users.list_for_admin(q=q or None, cursor=cursor, limit=limit)
        has_more = len(rows) > limit
        rows = rows[:limit]
        return UserAdminPage(
            items=[_user_out(u) for u in rows],
            next_cursor=rows[-1].id if has_more else None,
        )

    async def update_user(self, admin: User, user_id: int, data: UserAdminUpdate) -> UserAdminOut:
        target = await self.users.get(user_id)
        if target is None:
            raise NotFound("Пользователь не найден")
        if not role_policy.can_change_user(admin, target):
            raise AppError("Нельзя менять собственную роль и блокировку")

        if data.role is not None and data.role != target.role:
            self.audit.log(
                admin,
                "user.role_change",
                "user",
                target.id,
                {"username": target.username, "from": target.role.value, "to": data.role.value},
            )
            target.role = data.role

        if data.is_active is not None and data.is_active != target.is_active:
            target.is_active = data.is_active
            self.audit.log(
                admin,
                "user.unblock" if data.is_active else "user.block",
                "user",
                target.id,
                {"username": target.username},
            )
            if not data.is_active:
                await self.tokens.revoke_all_for_user(target.id, utcnow())

        await self.session.commit()
        return _user_out(target)

    async def list_audit(self, *, cursor: int | None, limit: int) -> AuditPage:
        rows = await self.audit.list_page(cursor=cursor, limit=limit)
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [
            AuditOut(
                id=entry.id,
                actor=UserBrief(id=entry.actor_id, handle=channel.handle, name=channel.name)
                if entry.actor_id is not None and channel is not None
                else None,
                action=entry.action,
                target_type=entry.target_type,
                target_id=entry.target_id,
                details=entry.details,
                created_at=entry.created_at,
            )
            for entry, channel in rows
        ]
        return AuditPage(items=items, next_cursor=rows[-1][0].id if has_more else None)