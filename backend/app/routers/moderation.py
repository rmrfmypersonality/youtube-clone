from fastapi import APIRouter

from app.core.deps import ModeratorUser, SessionDep
from app.core.params import CursorQuery, IdPath, LimitQuery
from app.models import ReportStatus
from app.schemas.moderation import HiddenOut, ReportPage
from app.services.moderation import ModerationService

router = APIRouter(prefix="/api/moderation", tags=["moderation"])


@router.get("/reports", response_model=ReportPage)
async def list_reports(
    moderator: ModeratorUser,
    session: SessionDep,
    status: ReportStatus = ReportStatus.open,
    cursor: CursorQuery = None,
    limit: LimitQuery = 20,
):
    """open: очередь от старых к новым; resolved и dismissed: история от новых к старым."""
    return await ModerationService(session).list_reports(status, cursor=cursor, limit=limit)


@router.post("/reports/{report_id}/dismiss", status_code=204)
async def dismiss_report(report_id: IdPath, moderator: ModeratorUser, session: SessionDep) -> None:
    await ModerationService(session).dismiss(moderator, report_id)


@router.post("/videos/{video_id}/hide", response_model=HiddenOut)
async def hide_video(video_id: IdPath, moderator: ModeratorUser, session: SessionDep):
    """Скрывает видео и закрывает все открытые жалобы на него как resolved."""
    return await ModerationService(session).set_video_hidden(moderator, video_id, True)


@router.post("/videos/{video_id}/unhide", response_model=HiddenOut)
async def unhide_video(video_id: IdPath, moderator: ModeratorUser, session: SessionDep):
    return await ModerationService(session).set_video_hidden(moderator, video_id, False)


@router.post("/comments/{comment_id}/hide", response_model=HiddenOut)
async def hide_comment(comment_id: IdPath, moderator: ModeratorUser, session: SessionDep):
    return await ModerationService(session).set_comment_hidden(moderator, comment_id, True)


@router.post("/comments/{comment_id}/unhide", response_model=HiddenOut)
async def unhide_comment(comment_id: IdPath, moderator: ModeratorUser, session: SessionDep):
    return await ModerationService(session).set_comment_hidden(moderator, comment_id, False)