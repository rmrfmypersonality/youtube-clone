from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.core.params import CursorQuery, LimitQuery
from app.schemas.notifications import NotificationCount, NotificationPage
from app.services.notifications import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPage)
async def list_notifications(
    user: CurrentUser, session: SessionDep, cursor: CursorQuery = None, limit: LimitQuery = 24
):
    """Видео каналов, на которые подписан пользователь, опубликованные после подписки."""
    return await NotificationService(session).list(user, cursor=cursor, limit=limit)


@router.get("/count", response_model=NotificationCount)
async def notifications_count(user: CurrentUser, session: SessionDep):
    """Сколько новых видео с момента последнего открытия уведомлений (не больше 100)."""
    return await NotificationService(session).count(user)


@router.post("/seen", status_code=204)
async def mark_seen(user: CurrentUser, session: SessionDep) -> None:
    await NotificationService(session).mark_seen(user)