from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, Conflict, NotFound
from app.core.time import utcnow
from app.models import Channel, Comment, Report, ReportStatus, User, Video
from app.policies import comments as comment_policy
from app.policies import reports as report_policy
from app.repositories.audit import AuditRepository
from app.repositories.channels import ChannelRepository
from app.repositories.comments import CommentRepository
from app.repositories.reports import ReportRepository
from app.repositories.videos import VideoRepository
from app.schemas.moderation import (
    HiddenOut,
    ReportCommentTarget,
    ReportCreate,
    ReportCreated,
    ReportItem,
    ReportPage,
    ReportVideoTarget,
    UserBrief,
)
from app.services.comments import COMMENT_NOT_FOUND
from app.services.video_access import VideoAccess

REPORT_NOT_FOUND = "Жалоба не найдена"


def _brief(channels: dict[int, Channel], user_id: int | None) -> UserBrief | None:
    channel = channels.get(user_id) if user_id is not None else None
    return UserBrief(id=user_id, handle=channel.handle, name=channel.name) if channel else None


def _item(
    report: Report,
    videos: dict[int, Video],
    comments: dict[int, Comment],
    channels: dict[int, Channel],
) -> ReportItem:
    video = videos.get(report.video_id) if report.video_id else None
    comment = comments.get(report.comment_id) if report.comment_id else None
    return ReportItem(
        id=report.id,
        status=report.status,
        reason=report.reason,
        details=report.details,
        created_at=report.created_at,
        handled_at=report.handled_at,
        reporter=_brief(channels, report.reporter_id),
        handled_by=_brief(channels, report.handled_by_id),
        video=ReportVideoTarget(
            id=video.id,
            title=video.title,
            visibility=video.visibility,
            hidden=video.hidden_by_moderation,
            owner=_brief(channels, video.owner_id),
        )
        if video
        else None,
        comment=ReportCommentTarget(
            id=comment.id,
            video_id=comment.video_id,
            text=comment.text,
            hidden=comment.hidden_by_moderation,
            author=_brief(channels, comment.user_id),
        )
        if comment
        else None,
    )


class ModerationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.access = VideoAccess(session)
        self.reports = ReportRepository(session)
        self.videos = VideoRepository(session)
        self.comments = CommentRepository(session)
        self.channels = ChannelRepository(session)
        self.audit = AuditRepository(session)

    # --- жалобы от пользователей ---

    async def _create(self, report: Report, duplicate_message: str) -> ReportCreated:
        self.reports.add(report)
        try:
            await self.session.commit()
        except IntegrityError:  # частичный уникальный индекс: открытая жалоба уже есть
            await self.session.rollback()
            raise Conflict(duplicate_message) from None
        return ReportCreated(id=report.id)

    async def report_video(self, user: User, video_id: int, data: ReportCreate) -> ReportCreated:
        video, _ = await self.access.visible(user, video_id)  # нет доступа = 404, как у зрителя
        if not report_policy.can_report_video(user, video):
            raise AppError("Нельзя пожаловаться на своё видео")
        return await self._create(
            Report(
                reporter_id=user.id, video_id=video.id, reason=data.reason, details=data.details
            ),
            "Вы уже отправили жалобу на это видео",
        )

    async def report_comment(
        self, user: User, comment_id: int, data: ReportCreate
    ) -> ReportCreated:
        comment = await self.comments.get(comment_id)
        if comment is None or not comment_policy.can_view_comment(user, comment):
            raise NotFound(COMMENT_NOT_FOUND)
        await self.access.visible(user, comment.video_id)
        if not report_policy.can_report_comment(user, comment):
            raise AppError("Нельзя пожаловаться на свой комментарий")
        return await self._create(
            Report(
                reporter_id=user.id,
                comment_id=comment.id,
                reason=data.reason,
                details=data.details,
            ),
            "Вы уже отправили жалобу на этот комментарий",
        )

    # --- очередь модератора ---

    async def list_reports(
        self, status: ReportStatus, *, cursor: int | None, limit: int
    ) -> ReportPage:
        rows = await self.reports.list_by_status(status, cursor=cursor, limit=limit)
        has_more = len(rows) > limit
        rows = rows[:limit]

        videos = {v.id: v for v in await self.videos.get_many({r.video_id for r in rows if r.video_id})}
        comments = {
            c.id: c for c in await self.comments.get_many({r.comment_id for r in rows if r.comment_id})
        }
        user_ids = (
            {r.reporter_id for r in rows}
            | {r.handled_by_id for r in rows if r.handled_by_id}
            | {v.owner_id for v in videos.values()}
            | {c.user_id for c in comments.values()}
        )
        channels = await self.channels.by_owner_ids(user_ids)

        return ReportPage(
            items=[_item(r, videos, comments, channels) for r in rows],
            next_cursor=rows[-1].id if has_more else None,
        )

    async def dismiss(self, moderator: User, report_id: int) -> None:
        report = await self.reports.get(report_id)
        if report is None:
            raise NotFound(REPORT_NOT_FOUND)
        if report.status != ReportStatus.open:
            raise Conflict("Жалоба уже обработана")
        report.status = ReportStatus.dismissed
        report.handled_by_id = moderator.id
        report.handled_at = utcnow()
        self.audit.log(
            moderator,
            "report.dismiss",
            "report",
            report.id,
            {"video_id": report.video_id, "comment_id": report.comment_id},
        )
        await self.session.commit()

    # --- скрытие и возврат ---

    async def set_video_hidden(self, moderator: User, video_id: int, hidden: bool) -> HiddenOut:
        # Права на просмотр не проверяем намеренно: модератор может скрыть и приватное видео,
        # но смотреть его это ему не даёт (can_view_video)
        video = await self.videos.get(video_id)
        if video is None:
            raise NotFound("Видео не найдено")
        if video.hidden_by_moderation != hidden:
            video.hidden_by_moderation = hidden
            if hidden:
                await self.reports.resolve_open(
                    video_id=video.id, handler_id=moderator.id, now=utcnow()
                )
            self.audit.log(
                moderator,
                "video.hide" if hidden else "video.unhide",
                "video",
                video.id,
                {"title": video.title, "owner_id": video.owner_id},
            )
            await self.session.commit()
        return HiddenOut(hidden=hidden)

    async def set_comment_hidden(
        self, moderator: User, comment_id: int, hidden: bool
    ) -> HiddenOut:
        comment = await self.comments.get(comment_id)
        if comment is None:
            raise NotFound(COMMENT_NOT_FOUND)
        if comment.hidden_by_moderation != hidden:
            comment.hidden_by_moderation = hidden
            if hidden:
                await self.reports.resolve_open(
                    comment_id=comment.id, handler_id=moderator.id, now=utcnow()
                )
            self.audit.log(
                moderator,
                "comment.hide" if hidden else "comment.unhide",
                "comment",
                comment.id,
                {"video_id": comment.video_id, "author_id": comment.user_id, "text": comment.text[:200]},
            )
            await self.session.commit()
        return HiddenOut(hidden=hidden)