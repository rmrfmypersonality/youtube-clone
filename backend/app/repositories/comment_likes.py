from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment, CommentLike


class CommentLikeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set(self, user_id: int, comment_id: int, value: int) -> None:
        await self.session.execute(
            insert(CommentLike)
            .values(user_id=user_id, comment_id=comment_id, value=value)
            .on_conflict_do_update(
                index_elements=["user_id", "comment_id"], set_={"value": value}
            )
        )

    async def remove(self, user_id: int, comment_id: int) -> None:
        await self.session.execute(
            delete(CommentLike).where(
                CommentLike.user_id == user_id, CommentLike.comment_id == comment_id
            )
        )

    async def recount(self, comment_id: int) -> int:
        """Пересчитывает likes_count по таблице: счётчик не может разойтись с реакциями."""
        likes = (
            select(func.count())
            .select_from(CommentLike)
            .where(CommentLike.comment_id == comment_id, CommentLike.value == 1)
            .scalar_subquery()
        )
        stmt = (
            update(Comment)
            .where(Comment.id == comment_id)
            .values(likes_count=likes)
            .returning(Comment.likes_count)
        )
        return (await self.session.execute(stmt)).scalar_one()