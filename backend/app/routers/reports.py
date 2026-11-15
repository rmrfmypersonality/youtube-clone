from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.core.params import IdPath
from app.schemas.moderation import ReportCreate, ReportCreated
from app.services.moderation import ModerationService

router = APIRouter(prefix="/api", tags=["reports"])


@router.post("/videos/{video_id}/report", response_model=ReportCreated, status_code=201)
async def report_video(video_id: IdPath, data: ReportCreate, user: CurrentUser, session: SessionDep):
    return await ModerationService(session).report_video(user, video_id, data)


@router.post("/comments/{comment_id}/report", response_model=ReportCreated, status_code=201)
async def report_comment(
    comment_id: IdPath, data: ReportCreate, user: CurrentUser, session: SessionDep
):
    return await ModerationService(session).report_comment(user, comment_id, data)