from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import SessionDep
from app.core.params import CursorQuery, LimitQuery
from app.schemas.videos import VideoPage
from app.services.feed import FeedService

router = APIRouter(prefix="/api", tags=["feed"])


@router.get("/videos", response_model=VideoPage)
async def home_feed(
    session: SessionDep,
    category: Annotated[str | None, Query(pattern=r"^[a-z0-9_]{1,32}$")] = None,
    cursor: CursorQuery = None,
    limit: LimitQuery = 24,
):
    """category: slug категории из /api/categories; неизвестный slug даёт пустую ленту."""
    return await FeedService(session).home(cursor=cursor, limit=limit, category=category)


@router.get("/search", response_model=VideoPage)
async def search_videos(
    session: SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=100)],
    cursor: CursorQuery = None,
    limit: LimitQuery = 24,
):
    return await FeedService(session).search(q, cursor=cursor, limit=limit)