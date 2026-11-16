from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.core.params import CursorQuery, LimitQuery
from app.schemas.auth import ChannelBrief
from app.schemas.videos import VideoPage
from app.services.channels import ChannelService
from app.services.feed import FeedService

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("", response_model=list[ChannelBrief])
async def my_subscriptions(user: CurrentUser, session: SessionDep):
    """Каналы, на которые подписан пользователь (до 200, по алфавиту)."""
    return await ChannelService(session).list_subscribed(user)


@router.get("/feed", response_model=VideoPage)
async def subscriptions_feed(
    user: CurrentUser, session: SessionDep, cursor: CursorQuery = None, limit: LimitQuery = 24
):
    """Публичные готовые видео каналов, на которые подписан пользователь, новые первыми."""
    return await FeedService(session).subscriptions(user.id, cursor=cursor, limit=limit)