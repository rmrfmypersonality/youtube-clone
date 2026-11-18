from sqlalchemy import Select, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Channel, Comment


def _visible(model, viewer_id: int | None, is_moderator: bool):
    """Скрытые модерацией комментарии видят только автор и модераторы."""
    if is_moderator:
        return true()
    cond = model.hidden_by_moderation.is_(False)
    if viewer_id is not None:
        cond = or_(cond, model.user_id == viewer_id)
    return cond


class CommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _base(viewer_id: int | None, is_moderator: bool) -> Select:
        reply = aliased(Comment)
        reply_count = (
            select(func.count())
            .select_from(reply)
            .where(reply.parent_id == Comment.id, _visible(reply, viewer_id, is_moderator))
            .correlate(Comment)
            .scalar_subquery()
        )
        return select(Comment, Channel, reply_count.label("reply_count")).join(
            Channel, Channel.owner_id == Comment.user_id
        )

    async def get(self, comment_id: int) -> Comment | None:
        return await self.session.get(Comment, comment_id)

    async def get_many(self, ids: set[int]) -> list[Comment]:
        if not ids:
            return []
        stmt = select(Comment).where(Comment.id.in_(ids))
        return list((await self.session.execute(stmt)).scalars())

    def add(self, comment: Comment) -> None:
        self.session.add(comment)

    async def list_top(
        self,
        video_id: int,
        *,
        cursor: int | None,
        limit: int,
        newest_first: bool,
        viewer_id: int | None,
        is_moderator: bool,
    ) -> list[tuple[Comment, Channel, int]]:
        stmt = self._base(viewer_id, is_moderator).where(
            Comment.video_id == video_id,
            Comment.parent_id.is_(None),
            _visible(Comment, viewer_id, is_moderator),
        )
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
        self,
        parent_id: int,
        *,
        cursor: int | None,
        limit: int,
        viewer_id: int | None,
        is_moderator: bool,
    ) -> list[tuple[Comment, Channel, int]]:
        stmt = self._base(viewer_id, is_moderator).where(
            Comment.parent_id == parent_id, _visible(Comment, viewer_id, is_moderator)
        )
        if cursor is not None:
            stmt = stmt.where(Comment.id > cursor)
        rows = (await self.session.execute(stmt.order_by(Comment.id.asc()).limit(limit + 1))).all()
        return [(r.Comment, r.Channel, r.reply_count) for r in rows]

    async def count_for_video(
        self, video_id: int, *, viewer_id: int | None, is_moderator: bool
    ) -> int:
        """Все комментарии и ответы под видео, видимые этому зрителю."""
        stmt = (
            select(func.count())
            .select_from(Comment)
            .where(Comment.video_id == video_id, _visible(Comment, viewer_id, is_moderator))
        )
        return (await self.session.execute(stmt)).scalar_one()