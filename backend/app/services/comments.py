from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound
from app.models import Channel, Comment, User, VideoStatus
from app.policies import comments as comment_policy
from app.policies.roles import can_moderate
from app.repositories.audit import AuditRepository
from app.repositories.comments import CommentRepository
from app.schemas.comments import CommentAuthor, CommentCreate, CommentOut, CommentPage, CommentCount
from app.services.video_access import VideoAccess

COMMENT_NOT_FOUND = "Комментарий не найден"


def _out(comment: Comment, channel: Channel, reply_count: int = 0) -> CommentOut:
    return CommentOut(
        id=comment.id,
        video_id=comment.video_id,
        parent_id=comment.parent_id,
        text=comment.text,
        created_at=comment.created_at,
        author=CommentAuthor(id=channel.owner_id, handle=channel.handle, name=channel.name),
        reply_count=reply_count,
        hidden_by_moderation=comment.hidden_by_moderation,
    )


def _page(rows: list[tuple[Comment, Channel, int]], limit: int) -> CommentPage:
    has_more = len(rows) > limit  # репозиторий берёт limit + 1, лишняя строка = есть следующая страница
    rows = rows[:limit]
    return CommentPage(
        items=[_out(c, ch, n) for c, ch, n in rows],
        next_cursor=rows[-1][0].id if has_more else None,
    )


def _viewer(user: User | None) -> dict:
    return {"viewer_id": user.id if user else None, "is_moderator": can_moderate(user)}


class CommentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.access = VideoAccess(session)
        self.comments = CommentRepository(session)
        self.audit = AuditRepository(session)

    async def list_for_video(
        self,
        user: User | None,
        video_id: int,
        *,
        sort: Literal["new", "old"],
        cursor: int | None,
        limit: int,
    ) -> CommentPage:
        await self.access.visible(user, video_id)
        rows = await self.comments.list_top(
            video_id, cursor=cursor, limit=limit, newest_first=sort == "new", **_viewer(user)
        )
        return _page(rows, limit)

    async def list_replies(
        self, user: User | None, comment_id: int, *, cursor: int | None, limit: int
    ) -> CommentPage:
        parent = await self.comments.get(comment_id)
        if (
            parent is None
            or parent.parent_id is not None  # ответы бывают только у корневых
            or not comment_policy.can_view_comment(user, parent)
        ):
            raise NotFound(COMMENT_NOT_FOUND)
        await self.access.visible(user, parent.video_id)
        rows = await self.comments.list_replies(
            parent.id, cursor=cursor, limit=limit, **_viewer(user)
        )
        return _page(rows, limit)

    async def create(self, user: User, video_id: int, data: CommentCreate) -> CommentOut:
        video, _ = await self.access.visible(user, video_id)
        if video.status != VideoStatus.ready:
            raise Conflict("Видео ещё не готово")

        parent_id = None
        if data.parent_id is not None:
            parent = await self.comments.get(data.parent_id)
            # Родитель должен быть из этого же видео и видимым автору ответа
            if (
                parent is None
                or parent.video_id != video.id
                or not comment_policy.can_view_comment(user, parent)
            ):
                raise NotFound(COMMENT_NOT_FOUND)
            parent_id = parent.parent_id or parent.id  # ответ на ответ уходит в корневой тред

        comment = Comment(video_id=video.id, user_id=user.id, parent_id=parent_id, text=data.text)
        self.comments.add(comment)
        await self.session.flush()
        await self.session.refresh(comment)  # подтягиваем created_at
        await self.session.commit()
        return _out(comment, user.channel)

    async def delete(self, user: User, comment_id: int) -> None:
        comment = await self.comments.get(comment_id)
        # Не автор и не админ: 404, чтобы не выдавать существование комментария
        if comment is None or not comment_policy.can_delete_comment(user, comment):
            raise NotFound(COMMENT_NOT_FOUND)
        if comment.user_id != user.id:  # действие админа над чужим
            self.audit.log(
                user,
                "comment.delete",
                "comment",
                comment.id,
                {"video_id": comment.video_id, "author_id": comment.user_id, "text": comment.text[:200]},
            )
        await self.session.delete(comment)  # ответы и жалобы удалит каскад в БД
        await self.session.commit()

    async def count(self, user: User | None, video_id: int) -> CommentCount:
        await self.access.visible(user, video_id)
        n = await self.comments.count_for_video(video_id, **_viewer(user))
        return CommentCount(count=n)