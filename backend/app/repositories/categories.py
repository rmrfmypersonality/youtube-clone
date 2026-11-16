from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category

DEFAULT_SLUG = "other"


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Category]:
        stmt = select(Category).order_by(Category.sort_order, Category.id)
        return list((await self.session.execute(stmt)).scalars())

    async def get(self, category_id: int) -> Category | None:
        return await self.session.get(Category, category_id)

    async def get_by_slug(self, slug: str) -> Category | None:
        result = await self.session.execute(select(Category).where(Category.slug == slug))
        return result.scalar_one_or_none()