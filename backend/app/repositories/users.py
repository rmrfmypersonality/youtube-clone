from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sql import escape_like
from app.models import Role, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    def add(self, user: User) -> None:
        self.session.add(user)

    async def list_for_admin(
        self, *, q: str | None, cursor: int | None, limit: int
    ) -> list[User]:
        stmt = select(User).order_by(User.id.desc()).limit(limit + 1)
        if cursor is not None:
            stmt = stmt.where(User.id < cursor)
        if q:
            pattern = f"%{escape_like(q)}%"
            stmt = stmt.where(
                or_(
                    User.username.ilike(pattern, escape="\\"),
                    User.email.ilike(pattern, escape="\\"),
                )
            )
        return list((await self.session.execute(stmt)).scalars().unique())

    async def has_other_active_admin(self, user_id: int) -> bool:
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role == Role.admin, User.is_active.is_(True), User.id != user_id)
        )
        return (await self.session.execute(stmt)).scalar_one() > 0