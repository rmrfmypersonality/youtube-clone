from typing import Literal

from fastapi import APIRouter

from app.core.deps import CurrentUser, OptionalUser, SessionDep
from app.core.params import CommentCursorQuery, CursorQuery, IdPath, LimitQuery, parse_comment_cursor
from app.schemas.comments import CommentCreate, CommentOut, CommentPage, CommentCount
from app.services.comments import CommentService
from app.schemas.reactions import ReactionIn, ReactionOut

router = APIRouter(prefix="/api", tags=["comments"])


@router.get("/videos/{video_id}/comments", response_model=CommentPage)
async def list_comments(
    video_id: IdPath,
    user: OptionalUser,
    session: SessionDep,
    sort: Literal["popular", "new"] = "new",
    cursor: CommentCursorQuery = None,
    limit: LimitQuery = 20,
):
    """sort=popular: лайки по убыванию; курсор вида «лайки_id». sort=new: курсор это id."""
    return await CommentService(session).list_for_video(
        user, video_id, sort=sort, cursor=parse_comment_cursor(sort, cursor), limit=limit
    )


@router.put("/comments/{comment_id}/reaction", response_model=ReactionOut)
async def react_to_comment(
    comment_id: IdPath, data: ReactionIn, user: CurrentUser, session: SessionDep
):
    """value: 1 лайк, -1 дизлайк, 0 снять реакцию."""
    return await CommentService(session).react(user, comment_id, data.value)


@router.get("/videos/{video_id}/comments/count", response_model=CommentCount)
async def comments_count(video_id: IdPath, user: OptionalUser, session: SessionDep):
    """Сколько комментариев (с ответами) видит этот пользователь."""
    return await CommentService(session).count(user, video_id)


@router.post("/videos/{video_id}/comments", response_model=CommentOut, status_code=201)
async def create_comment(
    video_id: IdPath, data: CommentCreate, user: CurrentUser, session: SessionDep
):
    return await CommentService(session).create(user, video_id, data)


@router.get("/comments/{comment_id}/replies", response_model=CommentPage)
async def list_replies(
    comment_id: IdPath,
    user: OptionalUser,
    session: SessionDep,
    cursor: CursorQuery = None,
    limit: LimitQuery = 20,
):
    return await CommentService(session).list_replies(user, comment_id, cursor=cursor, limit=limit)


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(comment_id: IdPath, user: CurrentUser, session: SessionDep) -> None:
    await CommentService(session).delete(user, comment_id)