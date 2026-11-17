from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.core.params import CursorQuery, IdPath, LimitQuery
from app.schemas.history import HistoryPage
from app.services.history import HistoryService

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=HistoryPage)
async def list_history(
    user: CurrentUser, session: SessionDep, cursor: CursorQuery = None, limit: LimitQuery = 24
):
    """Просмотренные видео, последние первыми. Закрытые от пользователя видео не показываются."""
    return await HistoryService(session).list(user, cursor=cursor, limit=limit)


@router.delete("", status_code=204)
async def clear_history(user: CurrentUser, session: SessionDep) -> None:
    await HistoryService(session).clear(user)


@router.delete("/{video_id}", status_code=204)
async def remove_from_history(video_id: IdPath, user: CurrentUser, session: SessionDep) -> None:
    await HistoryService(session).remove(user, video_id)