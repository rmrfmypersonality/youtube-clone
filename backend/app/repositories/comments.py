from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Channel, Comment


class CommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _base() -> Select:
        reply = aliased(Comment)
        reply_count = (
            select(func.count())
            .select_from(reply)
            .where(reply.parent_id == Comment.id)
            .correlate(Comment)
            .scalar_subquery()
        )
        return select(Comment, Channel, reply_count.label("reply_count")).join(
            Channel, Channel.owner_id == Comment.user_id
        )

    async def get(self, comment_id: int) -> Comment | None:
        return await self.session.get(Comment, comment_id)

    def add(self, comment: Comment) -> None:
        self.session.add(comment)

    async def list_top(
        self, video_id: int, *, cursor: int | None, limit: int, newest_first: bool
    ) -> list[tuple[Comment, Channel, int]]:
        stmt = self._base().where(Comment.video_id == video_id, Comment.parent_id.is_(None))
        if newest_first:
            if cursor is not None:
                stmt = stmt.where(Comment.id < cursor)
            stmt = stmt.order_by(Comment.id.desc())
        else:
            if cursor is not None:
                stmt = stmt.where(Comment.id > cursor)
            stmt = stmt.order_by(Comment.id.asc())
        rows = (await self.session.execute(stmt.limit(limit + 1))).all()
        return [(r.Comment, r.Channel, r.reply_count) for r in rows]

    async def list_replies(
        self, parent_id: int, *, cursor: int | None, limit: int
    ) -> list[tuple[Comment, Channel, int]]:
        stmt = self._base().where(Comment.parent_id == parent_id)
        if cursor is not None:
            stmt = stmt.where(Comment.id > cursor)
        rows = (await self.session.execute(stmt.order_by(Comment.id.asc()).limit(limit + 1))).all()
        return [(r.Comment, r.Channel, r.reply_count) for r in rows]